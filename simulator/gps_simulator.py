import json, math, os, random, time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
HOST=os.getenv("MQTT_HOST", "localhost"); PORT=int(os.getenv("MQTT_PORT", "1883"))
COUNT=int(os.getenv("VEHICLE_COUNT", "5")); INTERVAL=float(os.getenv("INTERVAL_SECONDS", "3"))
client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fleettrack-gps-simulator")
while True:
    try: client.connect(HOST, PORT, 30); break
    except Exception as e: print(f"Waiting for MQTT: {e}"); time.sleep(2)
client.loop_start()
# Demo route around Delhi NCR; positions are simulated and not actual vehicles.
center_lat, center_lon=28.6139, 77.2090
angles=[2*math.pi*i/max(COUNT,1) for i in range(COUNT)]
step=0
try:
    while True:
        for i, base in enumerate(angles):
            a=base + step*0.025
            payload={"vehicle_id":f"VH-{i+1:03d}","label":f"Delivery Van {i+1}","plate":f"DL01AB{1000+i}",
                     "latitude":center_lat+0.08*math.sin(a)+random.uniform(-0.001,0.001),
                     "longitude":center_lon+0.10*math.cos(a)+random.uniform(-0.001,0.001),
                     "speed_kph":round(random.uniform(0,115),1),"ignition_on":random.random()>0.08,
                     "recorded_at":datetime.now(timezone.utc).isoformat()}
            client.publish(f"fleet/telemetry/{payload['vehicle_id']}", json.dumps(payload), qos=1)
        step+=1; time.sleep(INTERVAL)
except KeyboardInterrupt: pass
finally: client.loop_stop(); client.disconnect()
