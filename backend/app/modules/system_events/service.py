from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EventSeverity
from app.core.exceptions import EventIdConflictError
from app.modules.system_events.models import SystemEvent


def record_event(
    session: Session,
    *,
    event_type: str,
    message: str,
    actor_type: str,
    severity: EventSeverity = EventSeverity.INFO,
    actor_user_id: UUID | None = None,
    order_id: UUID | None = None,
    mission_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    event_id: str | None = None,
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> tuple[SystemEvent, bool]:
    if event_id:
        existing = session.scalar(select(SystemEvent).where(SystemEvent.event_id == event_id))
        if existing:
            expected_metadata = metadata or {}
            is_compatible_replay = (
                existing.actor_user_id == actor_user_id
                and existing.actor_type == actor_type
                and existing.order_id == order_id
                and existing.mission_id == mission_id
                and existing.vehicle_id == vehicle_id
                and existing.event_type == event_type
                and existing.severity == severity
                and existing.message == message
                and existing.event_metadata == expected_metadata
            )
            if not is_compatible_replay:
                raise EventIdConflictError(
                    "event_id já foi usado com missão, tipo, estado ou payload diferente"
                )
            return existing, False
    event = SystemEvent(
        event_id=event_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        order_id=order_id,
        mission_id=mission_id,
        vehicle_id=vehicle_id,
        event_type=event_type,
        severity=severity,
        message=message,
        event_metadata=metadata or {},
    )
    session.add(event)
    return event, True
