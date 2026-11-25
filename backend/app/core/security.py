"""Security utilities: Argon2id password hashing, JWT tokens, and Trust IDs."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_password_hasher = PasswordHasher()
_TRUST_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CLEAN_RE = re.compile(r"[^A-Z0-9]")


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(
    *,
    user_id: int,
    role: str,
    company_id: int | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = utc_now()
    expire_delta = timedelta(
        minutes=expires_minutes if expires_minutes is not None else settings.JWT_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "company_id": company_id,
        "iat": now,
        "exp": now + expire_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token; return None if invalid/expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.PyJWTError:
        return None


def generate_trust_id() -> str:
    """Generate a cryptographically random Trust ID (TL-XXXX-XXXX-XXXX-XXXX)."""
    groups = [
        "".join(secrets.choice(_TRUST_ID_ALPHABET) for _ in range(4))
        for _ in range(4)
    ]
    return "TL-" + "-".join(groups)


def normalize_trust_id(raw_trust_id: str) -> str:
    """Normalize a user-entered Trust ID to canonical TL-XXXX-XXXX-XXXX-XXXX form."""
    cleaned = _CLEAN_RE.sub("", raw_trust_id.strip().upper())
    if cleaned.startswith("TL") and len(cleaned) == 18:
        body = cleaned[2:]
        return f"TL-{body[0:4]}-{body[4:8]}-{body[8:12]}-{body[12:16]}"
    if len(cleaned) == 16:
        return f"TL-{cleaned[0:4]}-{cleaned[4:8]}-{cleaned[8:12]}-{cleaned[12:16]}"
    return raw_trust_id.strip().upper()


def hash_token(value: str) -> str:
    """Return SHA-256 hex digest for high-entropy tokens (Trust IDs, session keys)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_session_key() -> str:
    """Generate a cryptographically random anonymous customer session key."""
    return secrets.token_urlsafe(32)
