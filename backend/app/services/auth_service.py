import uuid

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.rate_limit import LoginThrottle
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import User
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository

INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(
        self,
        db: Session,
        users: UserRepository,
        settings: Settings,
        throttle: LoginThrottle,
    ) -> None:
        self.db = db
        self.users = users
        self.settings = settings
        self.throttle = throttle

    def register(self, *, email: str, full_name: str, password: str) -> User:
        """Public sign-up always creates a customer. Admins are never created through the API."""
        if self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists")
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.CUSTOMER.value,
        )
        try:
            self.users.add(user)
            self.db.commit()
        except IntegrityError:  # lost a race with a concurrent registration of the same email
            self.db.rollback()
            raise ConflictError("An account with this email already exists") from None
        return user

    def login(self, *, email: str, password: str) -> tuple[str, int]:
        """Returns (access token, lifetime in seconds)."""
        self.throttle.check(email)  # locked accounts are refused even with the right password

        user = self.users.get_by_email(email)
        password_ok = verify_password(password, user.password_hash if user else None)

        # One generic error for unknown email, wrong password and disabled account.
        if user is None or not password_ok or not user.is_active:
            self.throttle.record_failure(email)
            raise UnauthorizedError(INVALID_CREDENTIALS)

        self.throttle.reset(email)
        if password_needs_rehash(user.password_hash):  # transparently upgrade old parameters
            user.password_hash = hash_password(password)
            self.db.commit()
        return create_access_token(user.id, self.settings)

    def user_from_token(self, token: str) -> User:
        try:
            user_id: uuid.UUID = decode_access_token(token, self.settings)
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid or expired token") from None
        user = self.users.get(user_id)
        # Checked on every request, so disabling an account takes effect immediately.
        if user is None or not user.is_active:
            raise UnauthorizedError("Invalid or expired token")
        return user
