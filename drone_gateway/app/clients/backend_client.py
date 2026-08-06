from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.exceptions import BackendContractError, BackendUnavailableError
from app.models import (
    AuthorizedMission,
    ClaimResponse,
    GatewayCommand,
    GatewayCommandStatus,
    HeartbeatResponse,
    MissionStatus,
    TelemetrySnapshot,
    VehicleHealth,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class BackendClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.api_base_url.rstrip("/"),
            timeout=settings.backend_timeout_seconds,
            headers={
                "X-Gateway-API-Key": settings.gateway_api_key.get_secret_value(),
                "User-Agent": "devcore-drone-gateway/0.1",
            },
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        # httpx request keyword arguments are intentionally dynamic at this adapter boundary.
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendUnavailableError(f"Backend indisponível: {exc}") from exc
        if response.is_error:
            detail = response.text[:500]
            if response.status_code >= 500:
                raise BackendUnavailableError(f"Backend retornou {response.status_code}: {detail}")
            raise BackendContractError(f"Backend retornou {response.status_code}: {detail}")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise BackendContractError("Backend retornou JSON inválido.") from exc

    @classmethod
    def _model(cls, model: type[ModelT], response: httpx.Response) -> ModelT:
        try:
            return model.model_validate(cls._json(response))
        except ValidationError as exc:
            raise BackendContractError(
                f"Backend retornou contrato inválido para {model.__name__}."
            ) from exc

    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        body = {
            "gateway_id": self._settings.gateway_id,
            "vehicle_identifier": self._settings.vehicle_identifier,
            "vehicle_name": self._settings.vehicle_name,
            "autopilot_system": self._settings.autopilot_system,
            **health.model_dump(mode="json"),
        }
        response = await self._request("POST", "/api/v1/gateway/heartbeat", json=body)
        return self._model(HeartbeatResponse, response)

    async def authorized_missions(self) -> list[AuthorizedMission]:
        response = await self._request("GET", "/api/v1/gateway/missions/authorized")
        payload = self._json(response)
        if isinstance(payload, dict):
            if "items" not in payload:
                raise BackendContractError("Lista de missões autorizadas não contém o campo items.")
            payload = payload["items"]
        if not isinstance(payload, list):
            raise BackendContractError("Lista de missões autorizadas possui formato inválido.")
        try:
            return [AuthorizedMission.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise BackendContractError("Missão autorizada possui contrato inválido.") from exc

    async def claim(self, mission_id: UUID) -> ClaimResponse:
        response = await self._request(
            "POST",
            f"/api/v1/gateway/missions/{mission_id}/claim",
            json={"gateway_id": self._settings.gateway_id},
            headers={"Idempotency-Key": f"claim:{self._settings.gateway_id}:{mission_id}"},
        )
        return self._model(ClaimResponse, response)

    async def pending_commands(self, limit: int = 20) -> list[GatewayCommand]:
        response = await self._request(
            "GET",
            "/api/v1/gateway/commands/pending",
            params={"gateway_id": self._settings.gateway_id, "limit": limit},
        )
        payload = self._json(response)
        if not isinstance(payload, list):
            raise BackendContractError("Lista de comandos pendentes possui formato inválido.")
        try:
            return [GatewayCommand.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise BackendContractError("Comando pendente possui contrato inválido.") from exc

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        if status is GatewayCommandStatus.PENDING:
            raise BackendContractError("Gateway não pode restaurar comando para PENDING.")
        identifier = event_id or uuid4()
        await self._request(
            "POST",
            f"/api/v1/gateway/commands/{command_id}/ack",
            json={
                "event_id": str(identifier),
                "gateway_id": self._settings.gateway_id,
                "status": status,
                "detail": detail,
            },
        )
        return identifier

    async def report_upload(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        if status not in {MissionStatus.UPLOADING, MissionStatus.UPLOADED, MissionStatus.FAILED}:
            raise BackendContractError(f"Status de upload inválido: {status}")
        identifier = event_id or uuid4()
        await self._request(
            "POST",
            f"/api/v1/gateway/missions/{mission_id}/upload-status",
            json={"event_id": str(identifier), "status": status, "detail": detail},
        )
        return identifier

    async def report_status(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        identifier = event_id or uuid4()
        await self._request(
            "POST",
            f"/api/v1/gateway/missions/{mission_id}/status",
            json={"event_id": str(identifier), "status": status, "detail": detail},
        )
        return identifier

    async def report_telemetry(
        self,
        mission_id: UUID,
        vehicle_id: UUID,
        telemetry: TelemetrySnapshot,
        *,
        event_id: UUID | None = None,
    ) -> UUID:
        identifier = event_id or uuid4()
        body = {
            "event_id": str(identifier),
            "vehicle_id": str(vehicle_id),
            **telemetry.model_dump(mode="json"),
        }
        await self._request("POST", f"/api/v1/gateway/missions/{mission_id}/telemetry", json=body)
        return identifier

    async def report_event(
        self,
        mission_id: UUID,
        *,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, str | int | float | bool | None] | None = None,
        occurred_at: datetime | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        normalized_severity = severity.upper()
        if normalized_severity == "CRITICAL":
            normalized_severity = "ERROR"
        if normalized_severity not in {"INFO", "WARNING", "ERROR"}:
            raise BackendContractError(f"Severidade de evento inválida: {severity}.")
        identifier = event_id or uuid4()
        event_metadata = dict(metadata or {})
        if occurred_at is not None:
            event_metadata.setdefault("source_occurred_at", occurred_at.isoformat())
        await self._request(
            "POST",
            f"/api/v1/gateway/missions/{mission_id}/events",
            json={
                "event_id": str(identifier),
                "event_type": event_type,
                "severity": normalized_severity,
                "message": message,
                "metadata": event_metadata,
            },
        )
        return identifier

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
