import pytest

from app.main import _publish_connection_failure
from app.models import ConnectionState, OperationalSource, VehicleHealth


class OfflineVehicle:
    async def read_health(self) -> VehicleHealth:
        return VehicleHealth(
            source=OperationalSource.HARDWARE_REAL,
            connected=False,
            heartbeat=False,
            connection_state=ConnectionState.ERROR,
            connection_mode="direct",
            connection_topology="direct",
            connection_endpoint="COM7",
            serial_port="COM7",
            connection_baud=57600,
            connection_error="Porta COM7 ocupada ou com acesso negado.",
        )


class RecordingBackend:
    def __init__(self) -> None:
        self.health: VehicleHealth | None = None

    async def heartbeat(self, health: VehicleHealth) -> None:
        self.health = health


@pytest.mark.asyncio
async def test_connection_failure_is_published_as_offline_health() -> None:
    backend = RecordingBackend()

    await _publish_connection_failure(  # type: ignore[arg-type]
        backend,
        OfflineVehicle(),
    )

    assert backend.health is not None
    assert backend.health.connected is False
    assert backend.health.heartbeat is False
    assert backend.health.connection_state is ConnectionState.ERROR
    assert backend.health.connection_error == "Porta COM7 ocupada ou com acesso negado."
