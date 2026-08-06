from datetime import UTC, datetime

from pydantic import BaseModel

from app.core.config import Settings
from app.core.geo import distance_m
from app.models import ClaimResponse, VehicleHealth


class CheckResult(BaseModel):
    code: str
    passed: bool
    detail: str


class PreflightResult(BaseModel):
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[str]:
        return [check.code for check in self.checks if not check.passed]


def evaluate_preflight(
    health: VehicleHealth,
    claim: ClaimResponse,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> PreflightResult:
    current_time = now or datetime.now(UTC)
    expiry = claim.authorization_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    mission = claim.mission
    origin_known = health.origin_latitude is not None and health.origin_longitude is not None
    origin_matches = (
        origin_known
        and distance_m(
            health.origin_latitude or 0,
            health.origin_longitude or 0,
            mission.origin_latitude,
            mission.origin_longitude,
        )
        <= settings.max_origin_deviation_m
    )
    checks = [
        CheckResult(code="VEHICLE_CONNECTED", passed=health.connected, detail="Conexão MAVLink"),
        CheckResult(code="HEARTBEAT", passed=health.heartbeat, detail="Heartbeat válido"),
        CheckResult(
            code="VEHICLE_DISARMED", passed=not health.armed, detail="Upload com veículo desarmado"
        ),
        CheckResult(
            code="GPS_FIX", passed=health.gps_fix_type >= 3, detail="Fix GPS 3D ou superior"
        ),
        CheckResult(
            code="GPS_SATELLITES",
            passed=health.satellites >= settings.min_gps_satellites,
            detail=f"Mínimo {settings.min_gps_satellites} satélites",
        ),
        CheckResult(code="EKF", passed=health.ekf_ok, detail="EKF saudável"),
        CheckResult(
            code="BATTERY",
            passed=health.battery_percent >= settings.min_battery_percent,
            detail=f"Bateria mínima {settings.min_battery_percent}%",
        ),
        CheckResult(code="PREFLIGHT", passed=health.preflight_ok, detail="Preflight do veículo"),
        CheckResult(code="RTL", passed=health.rtl_configured, detail="RTL configurado"),
        CheckResult(code="GEOFENCE", passed=health.geofence_enabled, detail="Geofence habilitada"),
        CheckResult(
            code="ORIGIN",
            passed=origin_matches,
            detail=f"Origem conhecida e a até {settings.max_origin_deviation_m} m da missão",
        ),
        CheckResult(
            code="MISSION_DISTANCE",
            passed=mission.estimated_distance_m <= settings.max_mission_distance_m,
            detail=f"Distância máxima {settings.max_mission_distance_m} m",
        ),
        CheckResult(
            code="AUTHORIZATION_EXPIRY",
            passed=expiry > current_time,
            detail="Autorização vigente",
        ),
    ]
    return PreflightResult(checks=checks)


def evaluate_start_readiness(
    health: VehicleHealth,
    claim: ClaimResponse,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> PreflightResult:
    result = evaluate_preflight(health, claim, settings, now=now)
    checks = [check for check in result.checks if check.code != "VEHICLE_DISARMED"]
    checks.extend(
        (
            CheckResult(
                code="VEHICLE_ARMED",
                passed=health.armed,
                detail="Armamento realizado pelo operador",
            ),
            CheckResult(
                code="FLIGHT_MODE",
                passed=health.flight_mode.upper() == settings.required_start_flight_mode.upper(),
                detail=f"Modo exigido: {settings.required_start_flight_mode}",
            ),
        )
    )
    return PreflightResult(checks=checks)
