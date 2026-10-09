"""Password hashing and JWT issuing/verification.

Uses the ``bcrypt`` library directly rather than passlib: passlib 1.7.x
reads ``bcrypt.__about__``, which bcrypt 4+ removed, so the combination
raises on every hash.

Passwords are SHA-256 pre-hashed before bcrypt. bcrypt silently ignores
input past 72 bytes, which would make two long passwords sharing a prefix
interchangeable; hashing first maps any length to a fixed 64-byte digest.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from ..core.config import settings

ALGORITHM = settings.algorithm


class TokenError(Exception):
    """Raised when a token is missing, malformed or expired."""


def _prepare(password: str) -> bytes:
    """Map a password of any length onto a fixed-size, bcrypt-safe value."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)  # 44 bytes, well under bcrypt's 72 limit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed stored hash must fail closed, not raise a 500.
        return False


def create_access_token(
    subject: str | int,
    *,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError("Could not validate credentials.") from exc

    if payload.get("type") != "access":
        raise TokenError("Wrong token type.")
    if not payload.get("sub"):
        raise TokenError("Token is missing a subject.")
    return payload
