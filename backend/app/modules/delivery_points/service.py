from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import InvalidCoordinatesError, NotFoundError
from app.database.types import point_ewkt
from app.modules.delivery_points.models import DeliveryPoint
from app.modules.delivery_points.schemas import DeliveryPointInput, DeliveryPointValidation


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    radius_m = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    distance = radius_m * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
    return Decimal(str(distance)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_delivery_point(
    payload: DeliveryPointInput, settings: Settings
) -> DeliveryPointValidation:
    if not payload.region_confirmed:
        raise InvalidCoordinatesError(
            "Confirme primeiro a região aproximada", fields={"region_confirmed": "required"}
        )
    if not payload.exact_point_selected:
        raise InvalidCoordinatesError(
            "A segunda etapa de seleção manual é obrigatória",
            fields={"exact_point_selected": "required"},
        )
    if not payload.user_confirmed:
        raise InvalidCoordinatesError(
            "Confirme o ponto exato de entrega", fields={"user_confirmed": "required"}
        )
    if not payload.user_confirmed_safe_area:
        raise InvalidCoordinatesError(
            "Confirme que o ponto representa uma área aberta e controlada",
            fields={"user_confirmed_safe_area": "required"},
        )
    if payload.map_type.lower() not in {"satellite", "hybrid"}:
        raise InvalidCoordinatesError(
            "A confirmação final deve usar visão de satélite ou híbrida",
            fields={"map_type": "satellite_required"},
        )

    base_distance = haversine_distance_m(
        settings.maps_default_latitude,
        settings.maps_default_longitude,
        payload.final_latitude,
        payload.final_longitude,
    )
    approximate_distance = None
    if payload.approximate_latitude is not None and payload.approximate_longitude is not None:
        approximate_distance = haversine_distance_m(
            payload.approximate_latitude,
            payload.approximate_longitude,
            payload.final_latitude,
            payload.final_longitude,
        )
    return DeliveryPointValidation(
        valid=True,
        within_coverage=True,
        final_latitude=payload.final_latitude,
        final_longitude=payload.final_longitude,
        distance_from_approximate_m=approximate_distance,
        distance_from_base_m=base_distance,
        max_distance_m=None,
        map_type=payload.map_type,
    )


def create_delivery_point(
    session: Session,
    user_id: UUID,
    payload: DeliveryPointInput,
    settings: Settings,
    *,
    commit: bool = True,
) -> DeliveryPoint:
    validation = validate_delivery_point(payload, settings)
    point = DeliveryPoint(
        user_id=user_id,
        searched_address=payload.searched_address,
        address_reference=payload.address_reference,
        selection_source=payload.selection_source,
        approximate_latitude=payload.approximate_latitude,
        approximate_longitude=payload.approximate_longitude,
        final_latitude=payload.final_latitude,
        final_longitude=payload.final_longitude,
        location=point_ewkt(payload.final_latitude, payload.final_longitude),
        label=payload.label,
        instructions=payload.instructions,
        map_provider=payload.map_provider,
        map_type=payload.map_type.lower(),
        accuracy_meters=payload.accuracy_meters,
        region_confirmed=payload.region_confirmed,
        exact_point_selected=payload.exact_point_selected,
        user_confirmed=payload.user_confirmed,
        user_confirmed_safe_area=payload.user_confirmed_safe_area,
        distance_from_approximate_m=validation.distance_from_approximate_m,
        distance_from_base_m=validation.distance_from_base_m,
    )
    session.add(point)
    session.flush()
    if commit:
        session.commit()
        session.refresh(point)
    return point


def get_owned_point(session: Session, point_id: UUID, user_id: UUID) -> DeliveryPoint:
    point = session.scalar(
        select(DeliveryPoint).where(DeliveryPoint.id == point_id, DeliveryPoint.user_id == user_id)
    )
    if not point:
        raise NotFoundError("Ponto de entrega não encontrado")
    return point
