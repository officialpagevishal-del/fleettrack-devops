import json, os, threading, time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from .db import Base, engine, get_db, SessionLocal
from .models import Vehicle, Telemetry, Alert
from .schemas import TelemetryIn, VehicleOut, AlertOut

INGESTED = Counter("fleettrack_telemetry_ingested_total", "Telemetry points accepted")
ONLINE = Gauge("fleettrack_vehicles_known", "Vehicles with a latest record")
OVERSPEED = Counter("fleettrack_overspeed_alerts_total", "Overspeed alerts generated")
clients: set[WebSocket] = set()
latest_cache: dict[str, dict] = {}

async def broadcast(payload: dict):
    dead=[]
    for ws in list(clients):
        try: await ws.send_json(payload)
        except Exception: dead.append(ws)
    for ws in dead: clients.discard(ws)

def ingest(data: TelemetryIn, db: Session):
    # Ignore timestamps more than 10 minutes in the future; production should also enforce freshness/replay policy.
    recorded = data.recorded_at or datetime.now(timezone.utc)
    if recorded.tzinfo is None: recorded = recorded.replace(tzinfo=timezone.utc)
    if (recorded - datetime.now(timezone.utc)).total_seconds() > 600:
        raise HTTPException(status_code=422, detail="recorded_at is too far in the future")
    vehicle = db.get(Vehicle, data.vehicle_id)
    if vehicle is None:
        vehicle = Vehicle(id=data.vehicle_id, label=data.label, plate=data.plate)
        db.add(vehicle)
    db.flush()
    vehicle.label=data.label; vehicle.plate=data.plate
    vehicle.latitude=data.latitude; vehicle.longitude=data.longitude
    vehicle.speed_kph=data.speed_kph; vehicle.ignition_on=data.ignition_on; vehicle.last_seen=recorded
    point=Telemetry(vehicle_id=data.vehicle_id, latitude=data.latitude, longitude=data.longitude,
                    speed_kph=data.speed_kph, ignition_on=data.ignition_on, recorded_at=recorded)
    db.add(point)
    threshold=float(os.getenv("OVERSPEED_KPH", "100"))
    if data.speed_kph > threshold:
        db.add(Alert(vehicle_id=data.vehicle_id, kind="OVERSPEED", message=f"Speed exceeded {threshold:.0f} km/h", speed_kph=data.speed_kph))
        OVERSPEED.inc()
    db.commit(); db.refresh(vehicle)
    INGESTED.inc(); ONLINE.set(db.query(Vehicle).count())
    payload={"type":"telemetry","vehicle_id":vehicle.id,"label":vehicle.label,"plate":vehicle.plate,
             "latitude":vehicle.latitude,"longitude":vehicle.longitude,"speed_kph":vehicle.speed_kph,
             "ignition_on":vehicle.ignition_on,"last_seen":vehicle.last_seen.isoformat() if vehicle.last_seen else None}
    latest_cache[vehicle.id]=payload
    return payload

def mqtt_worker():
    try:
        import paho.mqtt.client as mqtt
        host=os.getenv("MQTT_HOST", "localhost"); port=int(os.getenv("MQTT_PORT", "1883"))
        def on_connect(client, userdata, flags, reason_code, properties): client.subscribe("fleet/telemetry/+")
        def on_message(client, userdata, msg):
            try:
                data=TelemetryIn.model_validate_json(msg.payload)
                with SessionLocal() as db: ingest(data, db)
            except Exception as exc: print(f"Rejected MQTT message on {msg.topic}: {exc}")
        client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fleettrack-api")
        client.on_connect=on_connect; client.on_message=on_message
        while True:
            try: client.connect(host, port, 30); client.loop_forever(retry_first_connection=True)
            except Exception as exc: print(f"MQTT reconnect: {exc}"); time.sleep(3)
    except Exception as exc: print(f"MQTT worker unavailable: {exc}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    thread=threading.Thread(target=mqtt_worker, daemon=True); thread.start()
    yield
app=FastAPI(title="FleetTrack API", version="1.0.0", lifespan=lifespan)
origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","POST"], allow_headers=["Content-Type","Authorization"])

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/api/vehicles", response_model=list[VehicleOut])
def list_vehicles(db: Session=Depends(get_db)):
    return db.query(Vehicle).order_by(Vehicle.id).all()

@app.get("/api/vehicles/{vehicle_id}/telemetry")
def vehicle_history(vehicle_id: str, limit: int=100, db: Session=Depends(get_db)):
    if limit < 1 or limit > 1000: raise HTTPException(422, "limit must be between 1 and 1000")
    if db.get(Vehicle, vehicle_id) is None: raise HTTPException(404, "vehicle not found")
    rows=db.query(Telemetry).filter(Telemetry.vehicle_id==vehicle_id).order_by(desc(Telemetry.recorded_at)).limit(limit).all()
    return [{"latitude":r.latitude,"longitude":r.longitude,"speed_kph":r.speed_kph,"ignition_on":r.ignition_on,"recorded_at":r.recorded_at.isoformat()} for r in rows]

@app.post("/api/telemetry")
def post_telemetry(data: TelemetryIn, db: Session=Depends(get_db)):
    # Demo endpoint. Add device/API authentication before production use.
    result=ingest(data, db)
    return {"accepted":True,"vehicle":result}

@app.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(limit: int=100, db: Session=Depends(get_db)):
    if limit < 1 or limit > 500: raise HTTPException(422, "limit must be between 1 and 500")
    return db.query(Alert).order_by(desc(Alert.created_at)).limit(limit).all()

@app.get("/metrics")
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.websocket("/ws/live")
async def live_socket(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        for payload in latest_cache.values(): await ws.send_json(payload)
        while True: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally: clients.discard(ws)
