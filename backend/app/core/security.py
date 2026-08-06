from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import AuthenticationError


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("A senha deve possuir ao menos 8 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: UUID, role: str, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_expire_minutes)
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64encode(
        json.dumps(
            {
                "sub": str(user_id),
                "role": role,
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
            },
            separators=(",", ":"),
        ).encode()
    )
    unsigned = f"{header}.{payload}"
    signature = hmac.new(settings.jwt_secret.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_b64encode(signature)}", settings.jwt_expire_minutes * 60


def decode_access_token(token: str, settings: Settings) -> dict[str, str | int]:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(
            settings.jwt_secret.encode(), unsigned.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise AuthenticationError("Token inválido")
        decoded_header = json.loads(_b64decode(header))
        decoded_payload = json.loads(_b64decode(payload))
        if decoded_header.get("alg") != "HS256":
            raise AuthenticationError("Algoritmo de token inválido")
        if int(decoded_payload["exp"]) <= int(datetime.now(UTC).timestamp()):
            raise AuthenticationError("Token expirado")
        if not decoded_payload.get("sub") or not decoded_payload.get("role"):
            raise AuthenticationError("Token incompleto")
        return decoded_payload
    except AuthenticationError:
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AuthenticationError("Token inválido") from exc
