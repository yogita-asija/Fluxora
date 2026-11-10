from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.v1.router import api_router
from app.core import metrics
from app.core.config import Settings, get_settings
from app.core.database import engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.metrics import MetricsMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        # Interactive docs are a development tool: not served in production.
        # They live under /api so a reverse proxy only needs to route /api/ and /health/.
        docs_url=None if settings.is_production else "/api/docs",
        openapi_url=None if settings.is_production else "/api/openapi.json",
        redoc_url=None,
    )

    # Explicit allow-lists instead of "*"; no cookies are used, so credentials stay disabled.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        max_age=600,
    )

    @app.middleware("http")
    async def api_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.url.path.startswith(settings.api_v1_prefix):
            # Responses carry personal data and tokens: keep them out of shared caches.
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Prometheus scrapes /metrics directly on each replica; the Nginx edge does not route it.
    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics.router)
    return app


app = create_app()
