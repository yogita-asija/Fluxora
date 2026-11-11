import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FailedOutboxEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    aggregate_id: uuid.UUID
    attempts: int
    last_error: str | None
    created_at: datetime


class OutboxStats(BaseModel):
    pending: int
    published: int
    failed: int
    oldest_pending_age_seconds: float
    recent_failed: list[FailedOutboxEvent]
