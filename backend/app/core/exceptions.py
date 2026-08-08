from __future__ import annotations

from collections.abc import Mapping


class DomainError(Exception):
    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(
        self,
        detail: str,
        *,
        fields: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.fields = dict(fields or {})


class AuthenticationError(DomainError):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"


class AuthorizationError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class InvalidStateError(ConflictError):
    code = "INVALID_STATE"


class InvalidCoordinatesError(DomainError):
    code = "INVALID_COORDINATES"
