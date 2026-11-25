import asyncio
import logging

from app.clients.backend_client import BackendClient
from app.core.config import MavlinkMode, Settings
from app.core.exceptions import BackendUnavailableError, ConfigurationError, GatewayError
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
    observation_only = runtime_observation_only(settings)
    configure_logging(getattr(logging, settings.log_level))
    backend = BackendClient(settings)
    vehicle = build_vehicle_gateway(settings)
    executor = MissionExecutor(settings, backend, vehicle, observation_only=observation_only)
    connected = False
    reconnect_delay = settings.mavlink_reconnect_initial_seconds
    backend_failures = 0
    try:
        while True:
            if not connected:
                try:
                    await vehicle.connect(passive=observation_only)
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
                delay = min(
                    30.0, settings.gateway_poll_interval_seconds * 2 ** min(backend_failures, 12)
                )
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
            interval = settings.gateway_poll_interval_seconds
            if settings.px4_sitl_plan_validation:
                interval = min(interval, 0.15)
            await asyncio.sleep(interval)
    finally:
        await vehicle.close()
        await backend.close()


def runtime_observation_only(settings: Settings) -> bool:
    if settings.mavlink_mode is MavlinkMode.SIMULATION or settings.px4_sitl_plan_validation:
        return False
    if (
        settings.is_px4_bench_arm
        or settings.allow_vehicle_arm
        or settings.allow_flight_commands
        or settings.allow_mission_start
        or settings.allow_mission_upload
        or settings.allow_telemetry_requests
    ):
        raise ConfigurationError("O gateway operacional recebe telemetria passivamente.")
    return True


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("gateway stopped by operator")


if __name__ == "__main__":
    main()
