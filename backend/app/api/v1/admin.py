from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession
from app.repositories.outbox_repository import OutboxRepository
from app.schemas.admin import OutboxStats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/outbox", response_model=OutboxStats, summary="Outbox relay backlog (admin only)")
def outbox_stats(_: AdminUser, db: DbSession) -> OutboxStats:
    repo = OutboxRepository(db)
    stats = repo.stats(now=datetime.now(UTC))
    return OutboxStats(**stats, recent_failed=repo.recent_failed())
