from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import GatewayCommandStatus, GatewayCommandType, MissionStatus


class MissionWaypointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    command: int
    frame: int
    current: int
    autocontinue: int
    param1: float
    param2: float
    param3: float
    param4: float
    latitude: Decimal
    longitude: Decimal
    altitude_m: Decimal
    label: str


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    vehicle_id: UUID | None
    status: MissionStatus
    origin_latitude: Decimal
    origin_longitude: Decimal
    destination_latitude: Decimal
    destination_longitude: Decimal
    takeoff_altitude_m: Decimal
    estimated_distance_m: Decimal
    mission_sha256: str
    version: int
    exported_at: datetime | None
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    claimed_by_gateway: str | None
    claimed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    waypoints: list[MissionWaypointRead]


class MissionReview(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class PreflightChecklist(BaseModel):
    mission_planner_reviewed: bool
    controlled_area_secured: bool
    operator_ready: bool
    payload_secured: bool
    weather_checked: bool


class FlightAuthorizationCreate(BaseModel):
    vehicle_id: UUID
    operator_name: str = Field(min_length=2, max_length=120)
    controlled_area_confirmed: bool
    checklist: PreflightChecklist


class FlightAuthorizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mission_id: UUID
    status: str
    mission_version: int
    issued_at: datetime
    expires_at: datetime


class MissionAuthorizationResult(BaseModel):
    mission: MissionRead
    authorization: FlightAuthorizationRead


class GatewayClaim(BaseModel):
    gateway_id: str = Field(min_length=2, max_length=120)


class GatewayClaimResult(BaseModel):
    mission: MissionRead
    mission_file: str
    authorization_id: UUID
    authorization_expires_at: datetime


class GatewayUploadStatus(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    status: MissionStatus
    detail: str | None = Field(default=None, max_length=1000)


class GatewayMissionStatus(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    status: MissionStatus
    detail: str | None = Field(default=None, max_length=1000)


class GatewayCommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mission_id: UUID
    command: GatewayCommandType
    status: GatewayCommandStatus
    gateway_id: str | None
    requested_at: datetime
    acknowledged_at: datetime | None
    completed_at: datetime | None
    result_detail: str | None


class GatewayCommandAck(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    gateway_id: str = Field(min_length=2, max_length=120)
    status: GatewayCommandStatus
    detail: str | None = Field(default=None, max_length=1000)
