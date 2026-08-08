from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from app.core.enums import UserRole
from app.core.security import hash_password
from app.database.session import SessionLocal, initialize_database
from app.modules.users.models import User


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rotaciona explicitamente a senha de um administrador existente."
    )
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_INITIAL_EMAIL"),
        help="E-mail do administrador; padrão: ADMIN_INITIAL_EMAIL.",
    )
    return parser.parse_args()


def _new_password() -> str:
    from_environment = os.getenv("ADMIN_NEW_PASSWORD")
    if from_environment:
        return from_environment
    password = getpass.getpass("Nova senha administrativa: ")
    confirmation = getpass.getpass("Confirme a nova senha: ")
    if password != confirmation:
        raise SystemExit("As senhas informadas não coincidem.")
    return password


def main() -> None:
    arguments = _arguments()
    email = (arguments.email or "").strip().lower()
    if not email:
        raise SystemExit("Informe --email ou ADMIN_INITIAL_EMAIL.")
    encoded = hash_password(_new_password())
    initialize_database()
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Administrador não encontrado: {email}")
        if user.role is not UserRole.ADMIN:
            raise SystemExit("A conta informada não possui o papel ADMIN.")
        user.password_hash = encoded
        session.commit()
    print(f"Senha administrativa rotacionada para {email}.")


if __name__ == "__main__":
    main()
