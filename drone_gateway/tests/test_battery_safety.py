from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_preflight import build_claim, healthy_vehicle

from app.core.config import Settings
from app.models import TelemetrySnapshot, VehicleHealth
from app.safety.preflight import evaluate_preflight, evaluate_start_readiness
from app.telemetry.normalizer import normalize_telemetry


@pytest.mark.parametrize("percentage", [None, 0, 10, 20, 25, 39.9, 40, 100])
def test_battery_contracts_preserve_reported_value(percentage: float | None) -> None:
    health = VehicleHealth(connected=True, heartbeat=True, battery_percent=percentage)
    telemetry = TelemetrySnapshot(
        latitude=0,
        longitude=0,
        relative_altitude_m=0,
        ground_speed_m_s=0,
        recorded_at=datetime.now(UTC),
        battery_percent=percentage,
    )
    assert health.battery_percent == percentage
    assert telemetry.battery_percent == percentage


@pytest.mark.parametrize("percentage", [-1, 101, float("nan"), float("inf")])
def test_invalid_battery_is_rejected_by_both_contracts(percentage: float) -> None:
    with pytest.raises(ValidationError):
        VehicleHealth(connected=True, heartbeat=True, battery_percent=percentage)
    with pytest.raises(ValidationError):
        TelemetrySnapshot(
            latitude=0,
            longitude=0,
            relative_altitude_m=0,
            ground_speed_m_s=0,
            recorded_at=datetime.now(UTC),
            battery_percent=percentage,
        )


@pytest.mark.parametrize("percentage", [None, 0, 10, 20, 25, 39.9, 40, 100])
def test_preflight_and_start_enforce_battery_threshold(percentage: float | None) -> None:
    now = datetime.now(UTC)
    settings = Settings(_env_file=None, min_battery_percent=40)
    claim = build_claim(now + timedelta(minutes=2))
    health = healthy_vehicle().model_copy(update={"battery_percent": percentage})
    expected = percentage is not None and percentage >= 40
    preflight = evaluate_preflight(health, claim, settings, now=now)
    start = evaluate_start_readiness(
        health.model_copy(update={"armed": True, "flight_mode": "AUTO"}),
        claim,
        settings,
        now=now,
    )
    for result in (preflight, start):
        assert result.passed is expected
        assert result.failures == ([] if expected else ["BATTERY"])


@pytest.mark.parametrize(
    ("raw", "expected"), [(-1, None), (0, 0), (25, 25), (100, 100), (101, None)]
)
def test_normalizer_never_fabricates_full_charge(raw: int, expected: int | None) -> None:
    telemetry = normalize_telemetry(
        latitude_e7=0,
        longitude_e7=0,
        relative_altitude_mm=0,
        velocity_x_cm_s=0,
        velocity_y_cm_s=0,
        battery_percent=raw,
        gps_fix_type=3,
        satellites=16,
        flight_mode="STABILIZE",
        armed=False,
    )
    assert telemetry.battery_percent == expected


def test_default_battery_threshold_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIN_BATTERY_PERCENT", raising=False)
    assert Settings(_env_file=None).min_battery_percent == 40
