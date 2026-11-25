from uuid import UUID

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.core.exceptions import BackendContractError, GatewayError
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import BenchArmReport, OperationalSource


class BenchArmExecutor:
    def __init__(
        self, settings: Settings, backend: BackendClient, vehicle: PymavlinkVehicleGateway
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._vehicle = vehicle
        self._pending_report: tuple[UUID, BenchArmReport] | None = None

    async def _submit_report(self) -> None:
        if self._pending_report is not None:
            await self._backend.report_bench_arm(*self._pending_report)
            self._pending_report = None

    async def run_cycle(self) -> None:
        await self._submit_report()
        health = await self._vehicle.read_health()
        heartbeat = await self._backend.heartbeat(health)
        if (
            heartbeat.vehicle.identifier != self._settings.vehicle_identifier
            or heartbeat.vehicle.gateway_id != self._settings.gateway_id
        ):
            raise BackendContractError("Identidade do veículo de ensaio divergente.")
        if (
            health.source is not OperationalSource.HARDWARE_REAL
            or health.bench_arm_session_id is None
        ):
            return
        command = await self._backend.claim_bench_arm(
            heartbeat.vehicle.id, health.bench_arm_session_id
        )
        if command is None:
            return
        if command.vehicle_id != heartbeat.vehicle.id:
            raise BackendContractError("Solicitação pertence a outro veículo.")

        evidence = await self._vehicle.arm_bench(command)
        confirmed_snapshot_id = None
        detail = evidence.detail
        if evidence.armed_confirmed:
            try:
                observed = await self._vehicle.read_health()
                if observed.armed is True and observed.bench_arm_session_id == command.session_id:
                    response = await self._backend.heartbeat(observed)
                    if response.health and response.vehicle.id == command.vehicle_id:
                        confirmed_snapshot_id = response.health.id
            except GatewayError:
                confirmed_snapshot_id = None
            if confirmed_snapshot_id is None:
                detail = "ACK aceito. A confirmação do heartbeat armado não foi persistida."

        self._pending_report = (
            command.id,
            BenchArmReport(
                transmitted=evidence.transmitted,
                ack_result=evidence.ack_result,
                confirmed_snapshot_id=confirmed_snapshot_id,
                detail=detail,
            ),
        )
        await self._submit_report()
