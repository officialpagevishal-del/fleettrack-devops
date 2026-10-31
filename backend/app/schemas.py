from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class TelemetryIn(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    label: str = Field(default="Vehicle", max_length=120)
    plate: str = Field(default="", max_length=32)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kph: float = Field(ge=0, le=350)
    ignition_on: bool = False
    recorded_at: datetime | None = None

class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    plate: str
    latitude: float | None
    longitude: float | None
    speed_kph: float
    ignition_on: bool
    last_seen: datetime | None

class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehicle_id: str
    kind: str
    message: str
    speed_kph: float
    created_at: datetime
