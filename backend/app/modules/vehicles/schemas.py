from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.enums import OperationalSource, VehicleStatus


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identifier: str
    name: str
    autopilot_system: str
    autopilot_version: str | None
    operational_source: OperationalSource
    gateway_id: str
    status: VehicleStatus
    last_communication_at: datetime | None


class VehicleHealthInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    gateway_id: str = Field(min_length=2, max_length=120)
    vehicle_identifier: str = Field(min_length=1, max_length=120)
    vehicle_name: str = Field(default="Drone acadêmico", max_length=120)
    autopilot_system: str = Field(default="ArduPilot", max_length=80)
    autopilot_version: str | None = Field(default=None, max_length=120)
    source: OperationalSource = OperationalSource.UNKNOWN
    connected: bool
    heartbeat: bool
    gps_fix_type: int | None = Field(default=None, ge=0, le=8)
    satellites: int | None = Field(default=None, ge=0, le=100)
    ekf_ok: bool | None = None
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    battery_voltage: float | None = Field(default=None, ge=0, le=100)
    flight_mode: str | None = Field(default=None, max_length=40)
    armed: bool | None = None
    preflight_ok: bool | None = None
    rtl_configured: bool | None = None
    geofence_enabled: bool | None = None
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    connection_state: str | None = Field(default=None, max_length=40)
    connection_mode: str | None = Field(default=None, max_length=40)
    connection_topology: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("connection_topology", "topology"),
    )
    connection_endpoint: str | None = Field(
        default=None,
        max_length=240,
        validation_alias=AliasChoices("connection_endpoint", "endpoint"),
    )
    serial_port: str | None = Field(default=None, max_length=100)
    connection_baud: int | None = Field(
        default=None,
        ge=1,
        le=10_000_000,
        validation_alias=AliasChoices("connection_baud", "baud"),
    )
    mavlink_system_id: int | None = Field(
        default=None,
        ge=0,
        le=255,
        validation_alias=AliasChoices("mavlink_system_id", "system_id", "sysid"),
    )
    mavlink_component_id: int | None = Field(
        default=None,
        ge=0,
        le=255,
        validation_alias=AliasChoices("mavlink_component_id", "component_id", "compid"),
    )
    heartbeat_age_seconds: float | None = Field(default=None, ge=0)
    last_heartbeat_at: datetime | None = None
    current_latitude: float | None = Field(default=None, ge=-90, le=90)
    current_longitude: float | None = Field(default=None, ge=-180, le=180)
    current_altitude_m: float | None = Field(
        default=None,
        ge=-1000,
        le=100_000,
        validation_alias=AliasChoices("current_altitude_m", "relative_altitude_m"),
    )
    mission_upload_enabled: bool | None = None
    flight_commands_enabled: bool | None = None
    mission_start_enabled: bool | None = None
    vehicle_arm_enabled: bool | None = None
    connection_error: str | None = Field(default=None, max_length=2000)

    @field_validator("connection_endpoint", "serial_port", mode="before")
    @classmethod
    def sanitize_connection_endpoint(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        sanitized = value.strip().split("?", 1)[0].split("#", 1)[0]
        if "://" in sanitized:
            scheme, remainder = sanitized.split("://", 1)
            authority, separator, path = remainder.partition("/")
            authority = authority.rsplit("@", 1)[-1]
            sanitized = f"{scheme}://{authority}{separator}{path}"
        return sanitized or None

    @model_validator(mode="after")
    def validate_origin_pair(self) -> VehicleHealthInput:
        if (self.origin_latitude is None) != (self.origin_longitude is None):
            raise ValueError("A origem deve conter latitude e longitude")
        if (self.current_latitude is None) != (self.current_longitude is None):
            raise ValueError("A posição atual deve conter latitude e longitude")
        return self


class VehicleAuthorizationLimits(BaseModel):
    min_battery_percent: float
    battery_warning_percent: float
    min_gps_satellites: int


class VehicleHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vehicle_id: UUID
    connected: bool
    heartbeat: bool
    source: OperationalSource
    gps_fix_type: int | None
    satellites: int | None
    ekf_ok: bool | None
    battery_percent: float | None
    battery_voltage: float | None
    flight_mode: str | None
    armed: bool | None
    preflight_ok: bool | None
    rtl_configured: bool | None
    geofence_enabled: bool | None
    origin_latitude: Decimal | None
    origin_longitude: Decimal | None
    connection_state: str | None
    connection_mode: str | None
    connection_topology: str | None
    connection_endpoint: str | None
    serial_port: str | None
    connection_baud: int | None
    mavlink_system_id: int | None
    mavlink_component_id: int | None
    heartbeat_age_seconds: float | None
    last_heartbeat_at: datetime | None
    current_latitude: Decimal | None
    current_longitude: Decimal | None
    current_altitude_m: float | None
    mission_upload_enabled: bool | None
    flight_commands_enabled: bool | None
    mission_start_enabled: bool | None
    vehicle_arm_enabled: bool | None
    connection_error: str | None
    critical_state_hash: str
    captured_at: datetime
    received_at: datetime
    is_stale: bool
    authorization_limits: VehicleAuthorizationLimits


class VehicleHeartbeatResult(BaseModel):
    vehicle: VehicleRead
    health: VehicleHealthRead
    authorization_eligible: bool
    failures: list[str]
