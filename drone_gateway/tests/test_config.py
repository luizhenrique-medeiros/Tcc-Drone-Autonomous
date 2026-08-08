from app.core.config import Settings


def test_canonical_mavlink_baud_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("MAVLINK_BAUD", "115200")
    monkeypatch.delenv("MAVLINK_BAUD_RATE", raising=False)

    settings = Settings(_env_file=None)

    assert settings.mavlink_baud_rate == 115200


def test_legacy_mavlink_baud_rate_name_remains_compatible(monkeypatch) -> None:
    monkeypatch.delenv("MAVLINK_BAUD", raising=False)
    monkeypatch.setenv("MAVLINK_BAUD_RATE", "57600")

    settings = Settings(_env_file=None)

    assert settings.mavlink_baud_rate == 57600
