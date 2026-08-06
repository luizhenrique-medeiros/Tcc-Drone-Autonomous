import asyncio
import logging

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.core.exceptions import BackendUnavailableError, GatewayError
from app.core.logging import configure_logging
from app.mavlink.factory import build_vehicle_gateway
from app.missions.executor import MissionExecutor

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings()
    configure_logging()
    backend = BackendClient(settings)
    vehicle = build_vehicle_gateway(settings)
    executor = MissionExecutor(settings, backend, vehicle)
    connected = False
    backend_failures = 0
    try:
        while True:
            if not connected:
                try:
                    await vehicle.connect()
                    connected = True
                    logger.info(
                        "vehicle adapter connected",
                        extra={"gateway_id": settings.gateway_id},
                    )
                except GatewayError:
                    logger.warning("vehicle connection failed", exc_info=True)
                    await asyncio.sleep(min(30, settings.gateway_poll_interval_seconds * 2))
                    continue
            try:
                await executor.run_cycle()
                backend_failures = 0
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
