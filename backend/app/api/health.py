import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.schemas.common import LiveStatus, ReadyStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveStatus)
def live() -> LiveStatus:
    """Liveness: the process is up. Never touches dependencies."""
    return LiveStatus(status="ok")


@router.get("/ready", response_model=ReadyStatus)
def ready(db: DbSession, response: Response) -> ReadyStatus:
    """Readiness: dependencies the API needs to serve traffic. Currently PostgreSQL only;
    Redis/RabbitMQ/Kafka checks are added when the code starts using them."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyStatus(status="unavailable", checks={"database": "unavailable"})
    return ReadyStatus(status="ok", checks={"database": "ok"})
