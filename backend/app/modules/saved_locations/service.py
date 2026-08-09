from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.exceptions import ConflictError, InvalidCoordinatesError, NotFoundError
from app.database.types import point_ewkt
from app.modules.saved_locations.models import SavedLocation
from app.modules.saved_locations.schemas import (
    LOCATION_EVIDENCE_FIELDS,
    SavedLocationCreate,
    SavedLocationUpdate,
)
from app.modules.users.models import User

MAX_SAVED_LOCATIONS = 3
CONFIRMATION_FIELDS = (
    "region_confirmed",
    "exact_point_selected",
    "user_confirmed",
    "user_confirmed_safe_area",
)
ALLOWED_MAP_TYPES = {"hybrid", "satellite"}
COORDINATE_QUANTUM = Decimal("0.0000001")


class SavedLocationLimitReachedError(ConflictError):
    code = "SAVED_LOCATION_LIMIT_REACHED"


def _normalize_coordinate(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(COORDINATE_QUANTUM, rounding=ROUND_HALF_UP)


def saved_location_creation_lock(user_id: UUID) -> Select[tuple[UUID]]:
    return select(User.id).where(User.id == user_id).with_for_update(key_share=True)


def _validate_location_evidence(
    payload: SavedLocationCreate | SavedLocationUpdate,
    *,
    require_all_confirmations: bool,
) -> None:
    provided_fields = payload.model_fields_set
    if require_all_confirmations:
        missing = sorted(LOCATION_EVIDENCE_FIELDS.difference(provided_fields))
        if missing:
            raise InvalidCoordinatesError(
                "Envie coordenadas, mapa e confirmações da mesma revisão",
                fields={field: "required" for field in missing},
            )
    invalid = [
        field
        for field in CONFIRMATION_FIELDS
        if (require_all_confirmations or field in provided_fields)
        and getattr(payload, field) is not True
    ]
    if invalid:
        raise InvalidCoordinatesError(
            "As confirmações da localização devem ser verdadeiras",
            fields={field: "confirmation_required" for field in invalid},
        )
    if "map_type" in provided_fields and payload.map_type not in ALLOWED_MAP_TYPES:
        raise InvalidCoordinatesError(
            "A localização deve ser confirmada em mapa satélite ou híbrido",
            fields={"map_type": "satellite_required"},
        )


def list_saved_locations(session: Session, user_id: UUID) -> list[SavedLocation]:
    return list(
        session.scalars(
            select(SavedLocation)
            .where(SavedLocation.user_id == user_id)
            .order_by(SavedLocation.created_at.asc(), SavedLocation.id.asc())
        )
    )


def get_owned_saved_location(
    session: Session,
    location_id: UUID,
    user_id: UUID,
    *,
    for_update: bool = False,
) -> SavedLocation:
    query = select(SavedLocation).where(
        SavedLocation.id == location_id,
        SavedLocation.user_id == user_id,
    )
    if for_update:
        query = query.with_for_update()
    location = session.scalar(query)
    if not location:
        raise NotFoundError("Localização salva não encontrada")
    return location


def create_saved_location(
    session: Session,
    user_id: UUID,
    payload: SavedLocationCreate,
    *,
    commit: bool = True,
) -> SavedLocation:
    _validate_location_evidence(payload, require_all_confirmations=True)
    # PostgreSQL compiles key_share=True without read=True as FOR NO KEY UPDATE.
    # It serializes creators for this user while remaining compatible with the
    # parent-row KEY SHARE acquired by an idempotency record's foreign key.
    locked_user_id = session.scalar(saved_location_creation_lock(user_id))
    if locked_user_id is None:
        raise NotFoundError("Usuário não encontrado")

    current_count = session.scalar(
        select(func.count()).select_from(SavedLocation).where(SavedLocation.user_id == user_id)
    )
    if current_count is not None and current_count >= MAX_SAVED_LOCATIONS:
        raise SavedLocationLimitReachedError("Você pode salvar no máximo 3 localizações.")

    final_latitude = _normalize_coordinate(payload.final_latitude)
    final_longitude = _normalize_coordinate(payload.final_longitude)
    location = SavedLocation(
        user_id=user_id,
        name=payload.name,
        final_latitude=final_latitude,
        final_longitude=final_longitude,
        location=point_ewkt(final_latitude, final_longitude),
        address_reference=payload.address_reference,
        instructions=payload.instructions,
        accuracy_meters=payload.accuracy_meters,
        map_provider=payload.map_provider,
        map_type=payload.map_type,
        region_confirmed=payload.region_confirmed,
        exact_point_selected=payload.exact_point_selected,
        user_confirmed=payload.user_confirmed,
        user_confirmed_safe_area=payload.user_confirmed_safe_area,
    )
    session.add(location)
    session.flush()
    session.refresh(location)
    if commit:
        session.commit()
        session.refresh(location)
    return location


def update_saved_location(
    session: Session,
    location: SavedLocation,
    payload: SavedLocationUpdate,
) -> SavedLocation:
    changes = payload.model_dump(exclude_unset=True)
    coordinates_changed = "final_latitude" in changes
    evidence_changed = bool(payload.model_fields_set.intersection(LOCATION_EVIDENCE_FIELDS))
    _validate_location_evidence(
        payload,
        require_all_confirmations=evidence_changed,
    )
    if coordinates_changed:
        changes["final_latitude"] = _normalize_coordinate(payload.final_latitude)
        changes["final_longitude"] = _normalize_coordinate(payload.final_longitude)
    for field, value in changes.items():
        setattr(location, field, value)
    if coordinates_changed:
        location.location = point_ewkt(
            float(location.final_latitude),
            float(location.final_longitude),
        )
    session.commit()
    session.refresh(location)
    return location


def delete_saved_location(session: Session, location: SavedLocation) -> None:
    session.delete(location)
    session.commit()
