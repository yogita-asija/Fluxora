from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.rate_limit import LoginThrottle, get_login_throttle
from app.models import User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.order_service import OrderService
from app.services.product_service import ProductService

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ThrottleDep = Annotated[LoginThrottle, Depends(get_login_throttle)]

# auto_error=False so a missing header produces our own structured 401 (not FastAPI's 403).
bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


def get_product_service(db: DbSession) -> ProductService:
    return ProductService(ProductRepository(db))


def get_auth_service(db: DbSession, settings: SettingsDep, throttle: ThrottleDep) -> AuthService:
    return AuthService(db, UserRepository(db), settings, throttle)


def get_order_service(db: DbSession) -> OrderService:
    return OrderService(db, OrderRepository(db), ProductRepository(db))


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth: AuthServiceDep,
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication required")
    return auth.user_from_token(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise ForbiddenError("Administrator access required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
