from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    gateway_id: str = Field(min_length=2, max_length=120)
    vehicle_identifier: str = Field(min_length=1, max_length=120)
    vehicle_name: str = Field(default="Drone acadêmico", max_length=120)
    autopilot_system: str = Field(default="ArduPilot", max_length=80)
    autopilot_version: str | None = Field(default=None, max_length=120)
    source: OperationalSource = OperationalSource.UNKNOWN
    connected: bool
    heartbeat: bool
    gps_fix_type: int | None = Field(default=None, ge=0, le=6)
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

    @model_validator(mode="after")
    def validate_origin_pair(self) -> VehicleHealthInput:
        if (self.origin_latitude is None) != (self.origin_longitude is None):
            raise ValueError("A origem deve conter latitude e longitude")
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
