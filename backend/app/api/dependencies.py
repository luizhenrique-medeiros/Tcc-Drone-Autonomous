from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.modules.users.models import User

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    session: DatabaseSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Informe um token Bearer")
    claims = decode_access_token(credentials.credentials, settings)
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError as exc:
        raise AuthenticationError("Token inválido") from exc
    user = session.get(User, user_id)
    if not user or not user.active:
        raise AuthenticationError("Usuário inativo ou inexistente")
    if user.role.value != claims["role"]:
        raise AuthenticationError("Função do token não corresponde ao usuário")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise AuthorizationError("Esta ação exige a função ADMIN")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_customer(user: CurrentUser) -> User:
    if user.role != UserRole.CUSTOMER:
        raise AuthorizationError("Esta ação exige a função CUSTOMER")
    return user


CustomerUser = Annotated[User, Depends(require_customer)]


def require_gateway(
    settings: AppSettings,
    x_gateway_api_key: Annotated[str | None, Header(alias="X-Gateway-API-Key")] = None,
) -> None:
    if not x_gateway_api_key or not hmac.compare_digest(
        x_gateway_api_key, settings.gateway_api_key
    ):
        raise AuthenticationError("Credencial do gateway inválida")


GatewayAuth = Annotated[None, Depends(require_gateway)]
