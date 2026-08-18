from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConflictError, EventIdConflictError, NotFoundError
from app.modules.missions.models import Mission
from app.modules.telemetry.models import TelemetryLog
from app.modules.telemetry.schemas import TelemetryCreate, TelemetryRead
from app.modules.vehicles.models import Vehicle

COORDINATE_QUANTUM = Decimal("0.0000001")


def _normalize_coordinate(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(COORDINATE_QUANTUM, rounding=ROUND_HALF_UP)


def telemetry_is_stale(telemetry: TelemetryLog, settings: Settings) -> bool:
    received_at = telemetry.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return telemetry.is_stale or received_at < datetime.now(UTC) - timedelta(
        seconds=settings.heartbeat_timeout_seconds
    )


def telemetry_to_read(telemetry: TelemetryLog, settings: Settings) -> TelemetryRead:
    return TelemetryRead(
        id=telemetry.id,
        event_id=telemetry.event_id,
        mission_id=telemetry.mission_id,
        vehicle_id=telemetry.vehicle_id,
        source=telemetry.source,
        latitude=telemetry.latitude,
        longitude=telemetry.longitude,
        relative_altitude_m=telemetry.relative_altitude_m,
        ground_speed_m_s=telemetry.ground_speed_m_s,
        battery_percent=telemetry.battery_percent,
        gps_fix_type=telemetry.gps_fix_type,
        satellites=telemetry.satellites,
        flight_mode=telemetry.flight_mode,
        armed=telemetry.armed,
        recorded_at=telemetry.recorded_at,
        received_at=telemetry.received_at,
        is_stale=telemetry_is_stale(telemetry, settings),
    )


def record_telemetry(
    session: Session, mission: Mission, payload: TelemetryCreate, settings: Settings
) -> tuple[TelemetryLog, bool]:
    latitude = _normalize_coordinate(payload.latitude)
    longitude = _normalize_coordinate(payload.longitude)
    existing = session.scalar(select(TelemetryLog).where(TelemetryLog.event_id == payload.event_id))
    if existing:
        replay_matches = (
            existing.mission_id == mission.id
            and existing.vehicle_id == payload.vehicle_id
            and existing.source == payload.source
            and existing.latitude == latitude
            and existing.longitude == longitude
            and existing.relative_altitude_m == payload.relative_altitude_m
            and existing.ground_speed_m_s == payload.ground_speed_m_s
            and existing.battery_percent == payload.battery_percent
            and existing.gps_fix_type == payload.gps_fix_type
            and existing.satellites == payload.satellites
            and existing.flight_mode == payload.flight_mode
            and existing.armed == payload.armed
        )
        if payload.recorded_at is not None:
            expected_recorded_at = payload.recorded_at
            if expected_recorded_at.tzinfo is None:
                expected_recorded_at = expected_recorded_at.replace(tzinfo=UTC)
            actual_recorded_at = existing.recorded_at
            if actual_recorded_at.tzinfo is None:
                actual_recorded_at = actual_recorded_at.replace(tzinfo=UTC)
            replay_matches = replay_matches and actual_recorded_at == expected_recorded_at
        if not replay_matches:
            raise EventIdConflictError(
                "event_id da telemetria já foi usado com missão ou payload diferente"
            )
        return existing, False
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise NotFoundError("Veículo da telemetria não encontrado")
    if mission.vehicle_id != vehicle.id:
        raise ConflictError("O veículo não está associado à missão")
    if payload.source != vehicle.operational_source:
        raise ConflictError(
            "A origem da telemetria não corresponde à origem operacional publicada no heartbeat"
        )
    received_at = datetime.now(UTC)
    recorded_at = payload.recorded_at or received_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=UTC)
    if recorded_at > received_at + timedelta(seconds=settings.heartbeat_timeout_seconds):
        raise ConflictError("Horário da telemetria está adiantado em relação ao servidor")
    is_stale = recorded_at < received_at - timedelta(seconds=settings.heartbeat_timeout_seconds)
    latest = session.scalar(
        select(TelemetryLog)
        .where(TelemetryLog.mission_id == mission.id)
        .order_by(TelemetryLog.recorded_at.desc())
        .limit(1)
    )
    if latest:
        latest_at = latest.recorded_at
        if latest_at.tzinfo is None:
            latest_at = latest_at.replace(tzinfo=UTC)
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=UTC)
        if recorded_at < latest_at:
            raise ConflictError("Amostra de telemetria mais antiga que o estado persistido")
    telemetry = TelemetryLog(
        event_id=payload.event_id,
        mission_id=mission.id,
        vehicle_id=vehicle.id,
        source=payload.source,
        latitude=latitude,
        longitude=longitude,
        relative_altitude_m=payload.relative_altitude_m,
        ground_speed_m_s=payload.ground_speed_m_s,
        battery_percent=payload.battery_percent,
        gps_fix_type=payload.gps_fix_type,
        satellites=payload.satellites,
        flight_mode=payload.flight_mode,
        armed=payload.armed,
        recorded_at=recorded_at,
        received_at=received_at,
        is_stale=is_stale,
    )
    session.add(telemetry)
    session.commit()
    session.refresh(telemetry)
    return telemetry, True
