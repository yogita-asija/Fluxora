import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Deliberately simple: real validation of an address is sending it an email. This rejects
# obvious garbage without an extra dependency (and accepts internal domains like .local).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128  # caps hashing cost so huge passwords can't be used for DoS


def _normalise_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or not _EMAIL_RE.match(value):
        raise ValueError("must be a valid email address")
    return value


class _StrictModel(BaseModel):
    # Unknown fields are rejected, so a client can never smuggle in e.g. {"role": "admin"}.
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_StrictModel):
    email: str
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)

    _check_email = field_validator("email")(_normalise_email)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class LoginRequest(_StrictModel):
    email: str = Field(max_length=320)
    # No minimum here: login must not reveal the password policy or reject old passwords.
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    """Public view of a user. password_hash is intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime
