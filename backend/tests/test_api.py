from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app) as client:
        response=client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

def test_telemetry_validation():
    with TestClient(app) as client:
        response=client.post("/api/telemetry", json={"vehicle_id":"bad/id","latitude":200,"longitude":0,"speed_kph":20})
        assert response.status_code == 422
