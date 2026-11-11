import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session, aliased

from app.models import OutboxEvent
from app.models.enums import OutboxStatus


class OutboxRepository:
    """Data access for the outbox table. No publishing logic lives here."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def claim_batch(self, *, now: datetime, limit: int) -> Sequence[OutboxEvent]:
        """Lock up to `limit` events that are due, oldest first.

        - FOR UPDATE SKIP LOCKED: several relays can run at once without ever claiming the
          same row (rows locked by another relay are skipped, not waited for).
        - NOT EXISTS: an event is only eligible when no *earlier* event of the same aggregate
          is still unpublished (pending, backing off, or failed). Together with Kafka's
          key-based partitioning this keeps per-order ordering.
        The locks last until the caller's transaction ends.
        """
        earlier = aliased(OutboxEvent)
        blocked_by_earlier = exists().where(
            earlier.aggregate_id == OutboxEvent.aggregate_id,
            earlier.status != OutboxStatus.PUBLISHED.value,
            earlier.created_at < OutboxEvent.created_at,
        )
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING.value,
                OutboxEvent.available_at <= now,
                ~blocked_by_earlier,
            )
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return self.db.scalars(stmt).all()

    def stats(self, *, now: datetime) -> dict:
        counts = dict(
            self.db.execute(
                select(OutboxEvent.status, func.count()).group_by(OutboxEvent.status)
            ).all()
        )
        oldest = self.db.scalar(
            select(func.min(OutboxEvent.created_at)).where(
                OutboxEvent.status == OutboxStatus.PENDING.value
            )
        )
        if oldest is not None and oldest.tzinfo is None:  # SQLite returns naive datetimes
            oldest = oldest.replace(tzinfo=now.tzinfo)
        return {
            "pending": counts.get(OutboxStatus.PENDING.value, 0),
            "published": counts.get(OutboxStatus.PUBLISHED.value, 0),
            "failed": counts.get(OutboxStatus.FAILED.value, 0),
            "oldest_pending_age_seconds": (
                max(0.0, (now - oldest).total_seconds()) if oldest is not None else 0.0
            ),
        }

    def recent_failed(self, limit: int = 5) -> Sequence[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.FAILED.value)
            .order_by(OutboxEvent.created_at.desc())
            .limit(limit)
        )
        return self.db.scalars(stmt).all()

    def requeue_failed(self, *, now: datetime, event_id: uuid.UUID | None = None) -> int:
        """Give failed events a fresh set of attempts. Returns how many were requeued."""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.FAILED.value)
            .values(status=OutboxStatus.PENDING.value, attempts=0, available_at=now)
        )
        if event_id is not None:
            stmt = stmt.where(OutboxEvent.id == event_id)
        return self.db.execute(stmt).rowcount
