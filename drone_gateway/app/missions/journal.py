import json
import os
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.exceptions import ConfigurationError
from app.models import AuthorizedMission, ClaimResponse, MissionStatus


class JournalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: ClaimResponse | None = None
    offered_mission: AuthorizedMission | None = None
    phase: str
    pending_event_id: UUID | None = None
    upload_detail: str | None = None
    upload_uncertain_reported: bool = False
    verification_failure_reported: bool = False
    link_loss_reported: bool = False
    telemetry_stale_reported: bool = False
    start_uncertain_reported: bool = False
    binding_failure_reported: bool = False
    pending_status: MissionStatus | None = None
    pending_status_event_id: UUID | None = None
    last_reported_progress_status: MissionStatus | None = None


class MissionJournal:
    """Small atomic journal for the one active mission owned by this gateway."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> JournalRecord | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return JournalRecord.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ConfigurationError(
                f"Journal operacional inválido em {self._path}; intervenção é necessária."
            ) from exc

    def save(self, record: JournalRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self._path)

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)
