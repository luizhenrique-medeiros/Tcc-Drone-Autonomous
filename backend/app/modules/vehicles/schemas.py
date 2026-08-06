from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import VehicleStatus


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identifier: str
    name: str
    autopilot_system: str
    gateway_id: str
    status: VehicleStatus
    last_communication_at: datetime | None


class VehicleHealthInput(BaseModel):
    gateway_id: str = Field(min_length=2, max_length=120)
    vehicle_identifier: str = Field(min_length=1, max_length=120)
    vehicle_name: str = Field(default="Drone acadêmico", max_length=120)
    autopilot_system: str = Field(default="ArduPilot", max_length=80)
    connected: bool
    heartbeat: bool
    gps_fix_type: int = Field(ge=0, le=6)
    satellites: int = Field(ge=0, le=100)
    ekf_ok: bool
    battery_percent: float = Field(ge=0, le=100)
    battery_voltage: float | None = Field(default=None, ge=0, le=100)
    flight_mode: str = Field(max_length=40)
    armed: bool
    preflight_ok: bool
    rtl_configured: bool
    geofence_enabled: bool
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_origin_pair(self) -> VehicleHealthInput:
        if (self.origin_latitude is None) != (self.origin_longitude is None):
            raise ValueError("A origem deve conter latitude e longitude")
        return self


class VehicleHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vehicle_id: UUID
    connected: bool
    heartbeat: bool
    gps_fix_type: int
    satellites: int
    ekf_ok: bool
    battery_percent: float
    battery_voltage: float | None
    flight_mode: str
    armed: bool
    preflight_ok: bool
    rtl_configured: bool
    geofence_enabled: bool
    origin_latitude: Decimal | None
    origin_longitude: Decimal | None
    critical_state_hash: str
    captured_at: datetime


class VehicleHeartbeatResult(BaseModel):
    vehicle: VehicleRead
    health: VehicleHealthRead
    authorization_eligible: bool
    failures: list[str]
