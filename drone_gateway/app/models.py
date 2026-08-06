from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MissionStatus(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    EXECUTING = "EXECUTING"
    DESTINATION_REACHED = "DESTINATION_REACHED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    RETURNING = "RETURNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class GatewayCommandType(StrEnum):
    ABORT = "ABORT"
    RTL = "RTL"


class GatewayCommandStatus(StrEnum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GatewayCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    mission_id: UUID
    command: GatewayCommandType
    status: GatewayCommandStatus
    gateway_id: str | None = None
    requested_at: datetime
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    result_detail: str | None = None


class MissionWaypoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sequence: int = Field(ge=0)
    command: int = Field(ge=0)
    frame: int = Field(default=3, ge=0)
    current: int = Field(default=0, ge=0, le=1)
    autocontinue: int = Field(default=1, ge=0, le=1)
    param1: float = 0
    param2: float = 0
    param3: float = 0
    param4: float = 0
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: float = Field(ge=0, le=500)
    label: str | None = None


class AuthorizedMission(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    order_id: UUID
    vehicle_id: UUID | None = None
    status: MissionStatus
    origin_latitude: float = Field(ge=-90, le=90)
    origin_longitude: float = Field(ge=-180, le=180)
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)
    takeoff_altitude_m: float = Field(gt=0, le=120)
    estimated_distance_m: float = Field(ge=0)
    mission_sha256: str
    version: int = Field(gt=0)
    waypoints: list[MissionWaypoint] = Field(min_length=1)

    @field_validator("mission_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError("mission_sha256 deve conter 64 caracteres hexadecimais")
        return normalized


class ClaimResponse(BaseModel):
    mission: AuthorizedMission
    mission_file: str
    authorization_id: UUID
    authorization_expires_at: datetime


class HeartbeatVehicle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    identifier: str
    gateway_id: str


class HeartbeatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vehicle: HeartbeatVehicle
    authorization_eligible: bool
    failures: list[str] = Field(default_factory=list)


class VehicleHealth(BaseModel):
    connected: bool
    heartbeat: bool
    gps_fix_type: int = Field(ge=0, le=6)
    satellites: int = Field(ge=0, le=100)
    ekf_ok: bool
    battery_percent: float = Field(ge=0, le=100)
    battery_voltage: float | None = Field(default=None, ge=0)
    flight_mode: str = Field(max_length=40)
    armed: bool
    preflight_ok: bool
    rtl_configured: bool
    geofence_enabled: bool
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)


class TelemetrySnapshot(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    relative_altitude_m: float = Field(ge=-100, le=1000)
    ground_speed_m_s: float = Field(ge=0, le=200)
    battery_percent: float = Field(ge=0, le=100)
    gps_fix_type: int = Field(ge=0, le=6)
    satellites: int = Field(ge=0, le=100)
    flight_mode: str = Field(max_length=40)
    armed: bool
    recorded_at: datetime


class VehicleEvent(BaseModel):
    event_type: str
    severity: str
    message: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    occurred_at: datetime


class VehiclePoll(BaseModel):
    telemetry: TelemetrySnapshot
    suggested_status: MissionStatus | None = None
    events: list[VehicleEvent] = Field(default_factory=list)


class UploadResult(BaseModel):
    item_count: int = Field(ge=1)
    acknowledged: bool
    detail: str
