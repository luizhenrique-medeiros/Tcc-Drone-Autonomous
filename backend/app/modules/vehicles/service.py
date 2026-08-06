from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import VehicleStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.vehicles.models import Vehicle, VehicleHealthSnapshot
from app.modules.vehicles.schemas import VehicleHealthInput


def _critical_hash(payload: VehicleHealthInput) -> str:
    critical = {
        "connected": payload.connected,
        "heartbeat": payload.heartbeat,
        "gps_fix_type": payload.gps_fix_type,
        "satellites": payload.satellites,
        "ekf_ok": payload.ekf_ok,
        "battery_percent": round(payload.battery_percent, 1),
        "flight_mode": payload.flight_mode,
        "armed": payload.armed,
        "preflight_ok": payload.preflight_ok,
        "rtl_configured": payload.rtl_configured,
        "geofence_enabled": payload.geofence_enabled,
        "origin_latitude": payload.origin_latitude,
        "origin_longitude": payload.origin_longitude,
    }
    return hashlib.sha256(json.dumps(critical, sort_keys=True).encode()).hexdigest()


def health_failures(snapshot: VehicleHealthSnapshot, settings: Settings) -> list[str]:
    failures: list[str] = []
    captured_at = snapshot.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    if captured_at < datetime.now(UTC) - timedelta(seconds=settings.heartbeat_timeout_seconds):
        failures.append("HEARTBEAT_STALE")
    if not snapshot.connected or not snapshot.heartbeat:
        failures.append("NO_HEARTBEAT")
    if snapshot.gps_fix_type < 3 or snapshot.satellites < settings.min_gps_satellites:
        failures.append("GPS_INSUFFICIENT")
    if not snapshot.ekf_ok:
        failures.append("EKF_NOT_OK")
    if snapshot.battery_percent < settings.min_battery_percent:
        failures.append("BATTERY_LOW")
    if snapshot.armed:
        failures.append("VEHICLE_ALREADY_ARMED")
    if not snapshot.preflight_ok:
        failures.append("PREFLIGHT_NOT_OK")
    if not snapshot.rtl_configured:
        failures.append("RTL_NOT_CONFIGURED")
    if not snapshot.geofence_enabled:
        failures.append("GEOFENCE_NOT_ENABLED")
    if snapshot.origin_latitude is None or snapshot.origin_longitude is None:
        failures.append("ORIGIN_UNKNOWN")
    return failures


def record_heartbeat(
    session: Session, payload: VehicleHealthInput, settings: Settings
) -> tuple[Vehicle, VehicleHealthSnapshot, list[str]]:
    vehicle = session.scalar(
        select(Vehicle).where(Vehicle.identifier == payload.vehicle_identifier)
    )
    now = datetime.now(UTC)
    if vehicle and vehicle.gateway_id != payload.gateway_id:
        raise ConflictError("O veículo já está associado a outro gateway")
    if not vehicle:
        vehicle = Vehicle(
            identifier=payload.vehicle_identifier,
            name=payload.vehicle_name,
            autopilot_system=payload.autopilot_system,
            gateway_id=payload.gateway_id,
        )
        session.add(vehicle)
        session.flush()
    vehicle.name = payload.vehicle_name
    vehicle.autopilot_system = payload.autopilot_system
    vehicle.last_communication_at = now
    vehicle.status = (
        VehicleStatus.ONLINE if payload.connected and payload.heartbeat else VehicleStatus.OFFLINE
    )
    snapshot = VehicleHealthSnapshot(
        vehicle_id=vehicle.id,
        connected=payload.connected,
        heartbeat=payload.heartbeat,
        gps_fix_type=payload.gps_fix_type,
        satellites=payload.satellites,
        ekf_ok=payload.ekf_ok,
        battery_percent=payload.battery_percent,
        battery_voltage=payload.battery_voltage,
        flight_mode=payload.flight_mode,
        armed=payload.armed,
        preflight_ok=payload.preflight_ok,
        rtl_configured=payload.rtl_configured,
        geofence_enabled=payload.geofence_enabled,
        origin_latitude=payload.origin_latitude,
        origin_longitude=payload.origin_longitude,
        critical_state_hash=_critical_hash(payload),
        captured_at=now,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(vehicle)
    session.refresh(snapshot)
    return vehicle, snapshot, health_failures(snapshot, settings)


def latest_health(session: Session, vehicle_id: object) -> VehicleHealthSnapshot:
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise NotFoundError("Veículo não encontrado")
    snapshot = session.scalar(
        select(VehicleHealthSnapshot)
        .where(VehicleHealthSnapshot.vehicle_id == vehicle.id)
        .order_by(VehicleHealthSnapshot.captured_at.desc())
        .limit(1)
    )
    if not snapshot:
        raise NotFoundError("O veículo ainda não enviou estado de saúde")
    return snapshot
