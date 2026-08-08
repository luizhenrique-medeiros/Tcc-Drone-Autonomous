from datetime import UTC, datetime

from app.models import OperationalSource, TelemetrySnapshot


def normalize_telemetry(
    *,
    latitude_e7: int,
    longitude_e7: int,
    relative_altitude_mm: int,
    velocity_x_cm_s: int,
    velocity_y_cm_s: int,
    battery_percent: int,
    gps_fix_type: int,
    satellites: int,
    flight_mode: str,
    armed: bool,
    source: OperationalSource = OperationalSource.UNKNOWN,
    recorded_at: datetime | None = None,
) -> TelemetrySnapshot:
    ground_speed = (velocity_x_cm_s**2 + velocity_y_cm_s**2) ** 0.5 / 100
    return TelemetrySnapshot(
        source=source,
        latitude=latitude_e7 / 10_000_000,
        longitude=longitude_e7 / 10_000_000,
        relative_altitude_m=relative_altitude_mm / 1000,
        ground_speed_m_s=ground_speed,
        battery_percent=max(0, min(100, battery_percent)),
        gps_fix_type=max(0, gps_fix_type),
        satellites=max(0, satellites),
        flight_mode=flight_mode,
        armed=armed,
        recorded_at=recorded_at or datetime.now(UTC),
    )
