import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "handler", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds", ["method", "handler"]
)

router = APIRouter()


def handler_label(scope: Scope) -> str:
    """Full path with path-parameter values replaced by their names, e.g.
    /api/v1/products/{product_id}. Unmatched paths share one label so scanners
    can't blow up label cardinality."""
    if scope.get("route") is None:
        return "unmatched"
    segments = scope["path"].split("/")
    for name, value in reversed(list(scope.get("path_params", {}).items())):
        for i in range(len(segments) - 1, -1, -1):
            if segments[i] == str(value):
                segments[i] = "{" + name + "}"
                break
    return "/".join(segments)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class MetricsMiddleware:
    """Records request count and latency per route template (not raw path, to keep label
    cardinality bounded). Prometheus scrapes /metrics on each API replica directly."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            handler = handler_label(scope)
            REQUESTS.labels(scope["method"], handler, str(status_code)).inc()
            LATENCY.labels(scope["method"], handler).observe(time.perf_counter() - start)
