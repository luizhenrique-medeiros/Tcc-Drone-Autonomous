from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.enums import EventSeverity


class GatewayEventCreate(BaseModel):
    event_id: str = Field(min_length=6, max_length=120)
    vehicle_id: UUID | None = None
    event_type: str = Field(min_length=2, max_length=100)
    severity: EventSeverity = EventSeverity.INFO
    message: str = Field(min_length=1, max_length=2000)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SystemEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: str | None
    actor_user_id: UUID | None
    actor_type: str
    order_id: UUID | None
    mission_id: UUID | None
    vehicle_id: UUID | None
    event_type: str
    severity: EventSeverity
    message: str
    event_metadata: dict[str, str | int | float | bool | None] = Field(
        validation_alias=AliasChoices("event_metadata", "metadata"), serialization_alias="metadata"
    )
    created_at: datetime
