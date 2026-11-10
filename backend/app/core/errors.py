import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing errors."""

    status_code = 400
    code = "app_error"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class IdempotencyConflictError(ConflictError):
    code = "idempotency_key_reused"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"

    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message, headers={"Retry-After": str(max(1, retry_after))})


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Every error leaves the API in the same shape: {"error": {code, message, details}}."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
        return error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only location, message and type are returned: never the submitted input, which may
        # contain passwords.
        details = [
            {"loc": list(e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return error_response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return error_response(500, "internal_error", "An unexpected error occurred")
