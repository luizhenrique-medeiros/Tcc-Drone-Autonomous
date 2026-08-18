import asyncio
import logging

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.core.exceptions import BackendUnavailableError, GatewayError
from app.core.logging import configure_logging
from app.mavlink.factory import build_vehicle_gateway
from app.mavlink.vehicle_gateway import VehicleGateway
from app.missions.executor import MissionExecutor
from app.models import ConnectionState

logger = logging.getLogger(__name__)


async def _publish_connection_failure(
    backend: BackendClient,
    vehicle: VehicleGateway,
) -> None:
    """Best-effort publication of an honest offline/error hardware snapshot."""
    try:
        await backend.heartbeat(await vehicle.read_health())
    except GatewayError:
        logger.warning("could not publish vehicle connection failure", exc_info=True)


async def run() -> None:
    settings = Settings()
    configure_logging(getattr(logging, settings.log_level))
    backend = BackendClient(settings)
    vehicle = build_vehicle_gateway(settings)
    executor = MissionExecutor(settings, backend, vehicle)
    connected = False
    reconnect_delay = settings.mavlink_reconnect_initial_seconds
    backend_failures = 0
    try:
        while True:
            if not connected:
                try:
                    await vehicle.connect()
                    connected = True
                    reconnect_delay = settings.mavlink_reconnect_initial_seconds
                    logger.info(
                        "vehicle adapter connected",
                        extra={"gateway_id": settings.gateway_id},
                    )
                except GatewayError:
                    logger.warning("vehicle connection failed", exc_info=True)
                    await _publish_connection_failure(backend, vehicle)
                    await vehicle.close()
                    vehicle.mark_reconnecting()
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(
                        settings.mavlink_reconnect_max_seconds,
                        reconnect_delay * 2,
                    )
                    continue
            try:
                await executor.run_cycle()
                backend_failures = 0
                if vehicle.connection_state in {
                    ConnectionState.DISCONNECTED,
                    ConnectionState.STALE,
                    ConnectionState.ERROR,
                }:
                    connected = False
                    logger.warning(
                        "vehicle link requires reconnect",
                        extra={"gateway_id": settings.gateway_id},
                    )
                    await vehicle.close()
                    vehicle.mark_reconnecting()
            except BackendUnavailableError:
                backend_failures += 1
                delay = min(30.0, settings.gateway_poll_interval_seconds * 2**backend_failures)
                logger.warning(
                    "backend unavailable; retry scheduled",
                    extra={"gateway_id": settings.gateway_id},
                    exc_info=True,
                )
                await asyncio.sleep(delay)
                continue
            except GatewayError:
                connected = False
                logger.error("gateway cycle failed", exc_info=True)
                await vehicle.close()
                vehicle.mark_reconnecting()
            await asyncio.sleep(settings.gateway_poll_interval_seconds)
    finally:
        await vehicle.close()
        await backend.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("gateway stopped by operator")


if __name__ == "__main__":
    main()
