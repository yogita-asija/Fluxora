import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, in_values
from app.models.enums import OutboxStatus


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    """Transactional outbox: written in the same DB transaction as the change it describes,
    then published to the message brokers by a relay (added in a later phase)."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(in_values("status", OutboxStatus), name="status_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        # Relay polls oldest unpublished events; a partial index keeps that cheap.
        Index(
            "ix_outbox_events_pending_created_at",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
    )

    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=OutboxStatus.PENDING.value,
        server_default=OutboxStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(UUIDPrimaryKeyMixin, Base):
    """Idempotent-consumer ledger: a (event_id, consumer) pair is processed at most once."""

    __tablename__ = "processed_events"
    __table_args__ = (
        UniqueConstraint("event_id", "consumer", name="uq_processed_events_event_id_consumer"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    consumer: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
