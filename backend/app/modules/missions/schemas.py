from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.core.enums import (
    AuthorizationStatus,
    GatewayCommandStatus,
    GatewayCommandType,
    MissionStatus,
)


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


class MissionAuthorizationRead(BaseModel):
    id: UUID
    administrator_id: UUID
    administrator_name: str
    operator_name: str
    status: AuthorizationStatus
    mission_version: int
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None

    @field_validator("issued_at", "expires_at", "used_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class AdminMissionRead(MissionRead):
    authorization: MissionAuthorizationRead | None = None


class MissionReview(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class SafetyActionRequest(BaseModel):
    reason: str | None = Field(default=None, min_length=1, max_length=1000)


class VehicleArmRequest(BaseModel):
    """Explicit confirmations required for a normal, checked ARM request."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=10, max_length=1000)
    area_clear_confirmed: StrictBool
    operator_present_confirmed: StrictBool
    safety_switch_ready_confirmed: StrictBool

    @model_validator(mode="after")
    def require_all_confirmations(self) -> VehicleArmRequest:
        missing = [
            name
            for name in (
                "area_clear_confirmed",
                "operator_present_confirmed",
                "safety_switch_ready_confirmed",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError("Todas as confirmações presenciais devem ser verdadeiras")
        return self


class PreflightChecklist(BaseModel):
    area_and_conditions_clear: bool
    aircraft_and_payload_inspected: bool
    operator_ready: bool


class FlightAuthorizationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

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
    mission: AdminMissionRead
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
    reason: str | None
    status: GatewayCommandStatus
    gateway_id: str | None
    requested_at: datetime
    acknowledged_at: datetime | None
    completed_at: datetime | None
    result_detail: str | None


class VehicleArmResult(BaseModel):
    mission: AdminMissionRead
    command: GatewayCommandRead


class GatewayCommandAck(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    gateway_id: str = Field(min_length=2, max_length=120)
    status: GatewayCommandStatus
    detail: str | None = Field(default=None, max_length=1000)
