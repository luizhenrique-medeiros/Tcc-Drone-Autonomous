from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OperationalSource


class TelemetryCreate(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    vehicle_id: UUID
    source: OperationalSource = OperationalSource.UNKNOWN
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    relative_altitude_m: float = Field(ge=-100, le=1000)
    ground_speed_m_s: float = Field(ge=0, le=200)
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    gps_fix_type: int | None = Field(default=None, ge=0, le=6)
    satellites: int | None = Field(default=None, ge=0, le=100)
    flight_mode: str | None = Field(default=None, max_length=40)
    armed: bool | None = None
    recorded_at: datetime | None = None


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: str
    mission_id: UUID
    vehicle_id: UUID
    source: OperationalSource
    latitude: Decimal
    longitude: Decimal
    relative_altitude_m: float
    ground_speed_m_s: float
    battery_percent: float | None
    gps_fix_type: int | None
    satellites: int | None
    flight_mode: str | None
    armed: bool | None
    recorded_at: datetime
    received_at: datetime
    is_stale: bool
