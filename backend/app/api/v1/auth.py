from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUser, SettingsDep
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, auth: AuthServiceDep):
    return auth.register(
        email=payload.email, full_name=payload.full_name, password=payload.password
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, auth: AuthServiceDep):
    token, expires_in = auth.login(email=payload.email, password=payload.password)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
