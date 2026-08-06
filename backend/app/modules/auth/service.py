from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import UserRole
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.users.models import User
from app.modules.users.schemas import UserRead


def register_customer(session: Session, payload: RegisterRequest) -> User:
    existing = session.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise ConflictError("Já existe uma conta com este e-mail")
    user = User(
        role=UserRole.CUSTOMER,
        name=payload.name.strip(),
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(session: Session, payload: LoginRequest, settings: Settings) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == payload.email))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("E-mail ou senha inválidos")
    token, expires_in = create_access_token(user.id, user.role.value, settings)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


def seed_initial_admin(session: Session, settings: Settings) -> User | None:
    if not settings.admin_initial_email or not settings.admin_initial_password:
        return None
    email = settings.admin_initial_email.strip().lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing:
        return existing
    admin = User(
        role=UserRole.ADMIN,
        name=settings.admin_initial_name,
        email=email,
        password_hash=hash_password(settings.admin_initial_password),
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin
