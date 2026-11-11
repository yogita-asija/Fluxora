"""Outbox relay core: claim due events, publish them, record the outcome.

Delivery guarantee: **at least once.** An event is marked `published` only after the broker
acknowledged it, in the same transaction that holds its row lock. If the relay dies between
the broker ack and the commit, the row is still `pending` and is published again, so
consumers must be idempotent (they dedupe on the `event_id`, see `processed_events`).
"""
import json
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import OutboxEvent
from app.models.enums import OutboxStatus
from app.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)
MAX_ERROR_LENGTH = 500


@dataclass(frozen=True)
class OutboundMessage:
    event_id: str
    topic: str
    key: str
    value: bytes
    headers: dict[str, str]


class Publisher(Protocol):
    def publish_batch(self, messages: list[OutboundMessage]) -> dict[str, str | None]:
        """Send messages and wait for acknowledgements.

        Returns event_id -> None on success or an error string on failure. Must never raise
        for a per-message failure; a missing event_id is treated as a failure.
        """


@dataclass
class BatchResult:
    published: int = 0
    retried: int = 0
    failed: int = 0
    lags_seconds: tuple[float, ...] = ()

    @property
    def claimed(self) -> int:
        return self.published + self.retried + self.failed


def topic_for(settings: Settings, aggregate_type: str) -> str:
    return f"{settings.outbox_topic_prefix}.{aggregate_type}.events"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def backoff_seconds(settings: Settings, attempts: int) -> float:
    """Delay before retry number `attempts` (1-based): exponential, capped, with jitter so
    many failing events do not all retry at the same instant."""
    delay = min(
        settings.outbox_backoff_max_seconds,
        settings.outbox_backoff_base_seconds * (2 ** max(0, attempts - 1)),
    )
    return delay * random.uniform(0.8, 1.2)


def to_message(settings: Settings, event: OutboxEvent) -> OutboundMessage:
    occurred_at = _aware(event.created_at).isoformat()
    envelope = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id),
        "occurred_at": occurred_at,
        "payload": event.payload,
    }
    return OutboundMessage(
        event_id=str(event.id),
        topic=topic_for(settings, event.aggregate_type),
        key=str(event.aggregate_id),  # same order -> same partition -> ordered
        value=json.dumps(envelope, separators=(",", ":")).encode(),
        headers={
            "event_id": str(event.id),
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "occurred_at": occurred_at,
        },
    )


class OutboxRelay:
    def __init__(self, db: Session, publisher: Publisher, settings: Settings) -> None:
        self.db = db
        self.publisher = publisher
        self.settings = settings
        self.repo = OutboxRepository(db)

    def run_once(self, now: datetime | None = None) -> BatchResult:
        """Process one batch in one transaction. Row locks are held while publishing, which is
        bounded by the publish timeout; a crash simply releases the locks (events stay pending)."""
        now = now or datetime.now(UTC)
        events = self.repo.claim_batch(now=now, limit=self.settings.outbox_batch_size)
        if not events:
            self.db.rollback()
            return BatchResult()

        messages = [to_message(self.settings, event) for event in events]
        try:
            outcomes = self.publisher.publish_batch(messages)
        except Exception as exc:  # a broken publisher must not lose or skip events
            logger.exception("publisher failed for the whole batch")
            outcomes = {m.event_id: f"publisher error: {exc}" for m in messages}

        result = BatchResult()
        lags: list[float] = []
        for event in events:
            event.attempts += 1
            error = outcomes.get(str(event.id), "no acknowledgement from broker")
            if error is None:
                event.status = OutboxStatus.PUBLISHED.value
                event.published_at = now
                event.last_error = None
                lags.append(max(0.0, (now - _aware(event.created_at)).total_seconds()))
                result.published += 1
            elif event.attempts >= self.settings.outbox_max_attempts:
                event.status = OutboxStatus.FAILED.value
                event.last_error = error[:MAX_ERROR_LENGTH]
                result.failed += 1
                logger.error(
                    "outbox event %s moved to failed after %d attempts: %s",
                    event.id, event.attempts, error,
                )
            else:
                event.last_error = error[:MAX_ERROR_LENGTH]
                event.available_at = now + timedelta(
                    seconds=backoff_seconds(self.settings, event.attempts)
                )
                result.retried += 1
                logger.warning(
                    "outbox event %s publish failed (attempt %d), will retry: %s",
                    event.id, event.attempts, error,
                )
        self.db.commit()
        result.lags_seconds = tuple(lags)
        return result

    def requeue_failed(self, event_id: uuid.UUID | None = None) -> int:
        count = self.repo.requeue_failed(now=datetime.now(UTC), event_id=event_id)
        self.db.commit()
        return count
