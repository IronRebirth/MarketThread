from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()

ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    """Hash a plaintext password."""

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored hash."""

    return password_hash.verify(password, hashed_password)


def create_access_token(
    subject: str,
    session_version: int,
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT access token with explicit authentication claims."""

    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + expires_delta

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "typ": ACCESS_TOKEN_TYPE,
        "sv": session_version,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token."""

    settings = get_settings()

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={
            "require": [
                "sub",
                "iat",
                "exp",
                "iss",
                "typ",
                "sv",
            ],
        },
    )
