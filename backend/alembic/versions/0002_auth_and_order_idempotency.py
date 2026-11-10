"""auth credentials and per-user order idempotency

- users.password_hash: existing rows get the unusable placeholder "!" (nobody can log in
  until the seed script or a registration sets a real password).
- orders.request_hash: detects an Idempotency-Key reused with a different request.
- orders idempotency uniqueness becomes per user instead of global.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Added with a temporary default so existing rows satisfy NOT NULL, then the default is
    # dropped so new rows must always provide a real hash.
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default="!"),
    )
    op.alter_column("users", "password_hash", server_default=None)

    op.add_column("orders", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.drop_constraint("uq_orders_idempotency_key", "orders", type_="unique")
    op.create_unique_constraint(
        "uq_orders_user_id_idempotency_key", "orders", ["user_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_user_id_idempotency_key", "orders", type_="unique")
    op.create_unique_constraint("uq_orders_idempotency_key", "orders", ["idempotency_key"])
    op.drop_column("orders", "request_hash")
    op.drop_column("users", "password_hash")
