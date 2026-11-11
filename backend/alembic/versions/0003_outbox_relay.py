"""outbox relay: retry scheduling and ordering indexes

- outbox_events.available_at: an event is not published before this time (retry backoff).
- Replaces the pending index with one that matches the relay's polling query, and adds an
  index for the per-aggregate ordering check.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.drop_index("ix_outbox_events_pending_created_at", table_name="outbox_events")
    op.create_index(
        "ix_outbox_events_pending_available_at",
        "outbox_events",
        ["available_at", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_outbox_events_aggregate_unpublished",
        "outbox_events",
        ["aggregate_id", "created_at"],
        postgresql_where=sa.text("status <> 'published'"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_aggregate_unpublished", table_name="outbox_events")
    op.drop_index("ix_outbox_events_pending_available_at", table_name="outbox_events")
    op.create_index(
        "ix_outbox_events_pending_created_at",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_column("outbox_events", "available_at")
