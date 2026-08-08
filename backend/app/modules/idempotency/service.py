from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.modules.idempotency.models import IdempotencyRecord


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    body: dict[str, object]
    status_code: int
    replayed: bool


class IdempotencyConflictError(ConflictError):
    code = "IDEMPOTENCY_KEY_REUSED"


def request_fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _find_record(
    session: Session, user_id: UUID, operation: str, key: str
) -> IdempotencyRecord | None:
    return session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
    )


def _validate_replay(record: IdempotencyRecord, fingerprint: str) -> IdempotencyResult:
    if record.request_sha256 != fingerprint:
        raise IdempotencyConflictError(
            "A Idempotency-Key já foi usada com outro conteúdo",
            fields={"Idempotency-Key": "payload_mismatch"},
        )
    return IdempotencyResult(
        body=record.response_body,
        status_code=record.response_status,
        replayed=True,
    )


def execute_idempotently(
    session: Session,
    *,
    user_id: UUID,
    operation: str,
    key: str | None,
    request_payload: object,
    response_status: int,
    action: Callable[[], dict[str, object]],
) -> IdempotencyResult:
    fingerprint = request_fingerprint(request_payload)
    reserved: IdempotencyRecord | None = None
    if key:
        existing = _find_record(session, user_id, operation, key)
        if existing:
            return _validate_replay(existing, fingerprint)
        reserved = IdempotencyRecord(
            user_id=user_id,
            operation=operation,
            idempotency_key=key,
            request_sha256=fingerprint,
            response_status=response_status,
            response_body={},
        )
        session.add(reserved)
        try:
            # Reserve the unique key before executing side effects. On PostgreSQL,
            # a concurrent request with the same key waits for this transaction
            # and then replays the committed response instead of re-running the
            # action against an already changed domain state.
            session.flush()
        except IntegrityError:
            session.rollback()
            if record := _find_record(session, user_id, operation, key):
                return _validate_replay(record, fingerprint)
            raise
    try:
        body = action()
        if reserved:
            reserved.response_body = body
        session.commit()
        return IdempotencyResult(body=body, status_code=response_status, replayed=False)
    except IntegrityError:
        session.rollback()
        if key and (record := _find_record(session, user_id, operation, key)):
            return _validate_replay(record, fingerprint)
        raise
    except Exception:
        session.rollback()
        raise
