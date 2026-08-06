from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.missions.models import Mission
from app.modules.telemetry.models import TelemetryLog
from app.modules.telemetry.schemas import TelemetryCreate
from app.modules.vehicles.models import Vehicle


def record_telemetry(
    session: Session, mission: Mission, payload: TelemetryCreate
) -> tuple[TelemetryLog, bool]:
    existing = session.scalar(select(TelemetryLog).where(TelemetryLog.event_id == payload.event_id))
    if existing:
        return existing, False
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise NotFoundError("Veículo da telemetria não encontrado")
    if mission.vehicle_id != vehicle.id:
        raise ConflictError("O veículo não está associado à missão")
    recorded_at = payload.recorded_at or datetime.now(UTC)
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
        latitude=payload.latitude,
        longitude=payload.longitude,
        relative_altitude_m=payload.relative_altitude_m,
        ground_speed_m_s=payload.ground_speed_m_s,
        battery_percent=payload.battery_percent,
        gps_fix_type=payload.gps_fix_type,
        satellites=payload.satellites,
        flight_mode=payload.flight_mode,
        armed=payload.armed,
        recorded_at=recorded_at,
    )
    session.add(telemetry)
    session.commit()
    session.refresh(telemetry)
    return telemetry, True
