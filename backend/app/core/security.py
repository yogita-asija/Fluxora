"""Password hashing and JWT access tokens."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

ALGORITHM = "HS256"  # fixed on purpose: the algorithm is never taken from the token header

_hasher = PasswordHasher()  # argon2id with the library's RFC 9106 defaults

# Verifying against this when an account doesn't exist keeps login timing the same for
# "unknown email" and "wrong password", so response time doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("orderflow-dummy-password")

# Stored for accounts that have no usable password yet. It is not a valid hash, so it can
# never verify.
UNUSABLE_PASSWORD = "!"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """True only when `password` matches. Never raises for bad input or bad hashes."""
    try:
        matched = _hasher.verify(password_hash or _DUMMY_HASH, password)
        return matched and password_hash is not None
    except VerificationError:
        return False
    except InvalidHashError:
        # e.g. UNUSABLE_PASSWORD: still burn the same time as a real check.
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except VerificationError:
            pass
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def create_access_token(user_id: uuid.UUID, settings: Settings) -> tuple[str, int]:
    """Returns (token, lifetime in seconds). The token carries identity only: role and
    active status are read from the database on every request."""
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    claims = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Returns the user id, or raises jwt.InvalidTokenError for anything wrong with the token:
    bad signature, expired, wrong issuer, missing claims, unexpected algorithm."""
    claims = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "iss"]},
    )
    try:
        return uuid.UUID(claims["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("invalid subject") from exc
