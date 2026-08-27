from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MissionStatus(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"
    DESTINATION_REACHED = "DESTINATION_REACHED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    RETURNING = "RETURNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class OperationalSource(StrEnum):
    UNKNOWN = "UNKNOWN"
    SIMULATION = "SIMULATION"
    SITL = "SITL"
    HARDWARE_REAL = "HARDWARE_REAL"


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    WAITING_HEARTBEAT = "WAITING_HEARTBEAT"
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class GatewayCommandType(StrEnum):
    ARM = "ARM"
    START = "START"
    PAUSE = "PAUSE"
    CONTINUE = "CONTINUE"
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
    reason: str | None = None


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
    source: OperationalSource = OperationalSource.UNKNOWN
    autopilot_version: str | None = Field(default=None, max_length=120)
    connected: bool
    heartbeat: bool
    gps_fix_type: int | None = Field(default=None, ge=0, le=8)
    satellites: int | None = Field(default=None, ge=0, le=100)
    ekf_ok: bool | None = None
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    battery_voltage: float | None = Field(default=None, ge=0)
    flight_mode: str | None = Field(default=None, max_length=40)
    armed: bool | None = None
    preflight_ok: bool | None = None
    rtl_configured: bool | None = None
    geofence_enabled: bool | None = None
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    connection_mode: str | None = Field(default=None, max_length=40)
    connection_topology: str | None = Field(default=None, max_length=40)
    connection_endpoint: str | None = Field(default=None, max_length=240)
    serial_port: str | None = Field(default=None, max_length=100)
    connection_baud: int | None = Field(default=None, ge=1200, le=4_000_000)
    mavlink_system_id: int | None = Field(default=None, ge=1, le=255)
    mavlink_component_id: int | None = Field(default=None, ge=0, le=255)
    heartbeat_age_seconds: float | None = Field(default=None, ge=0)
    last_heartbeat_at: datetime | None = None
    current_latitude: float | None = Field(default=None, ge=-90, le=90)
    current_longitude: float | None = Field(default=None, ge=-180, le=180)
    current_altitude_m: float | None = Field(default=None, ge=-100, le=1000)
    mission_upload_enabled: bool = False
    flight_commands_enabled: bool = False
    mission_start_enabled: bool = False
    vehicle_arm_enabled: bool = False
    connection_error: str | None = Field(default=None, max_length=1000)


class TelemetrySnapshot(BaseModel):
    source: OperationalSource = OperationalSource.UNKNOWN
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    relative_altitude_m: float = Field(ge=-100, le=1000)
    ground_speed_m_s: float = Field(ge=0, le=200)
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    gps_fix_type: int | None = Field(default=None, ge=0, le=8)
    satellites: int | None = Field(default=None, ge=0, le=100)
    flight_mode: str | None = Field(default=None, max_length=40)
    armed: bool | None = None
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


class MissionVerificationResult(BaseModel):
    item_count: int = Field(ge=1)
    verified: bool
    detail: str


class VehicleArmResult(BaseModel):
    command_sent: bool
    command_acknowledged: bool
    armed_heartbeat_confirmed: bool
    external_state_reconciled: bool
