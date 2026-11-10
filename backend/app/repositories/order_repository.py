import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem, OutboxEvent

# Loading items and their products up front avoids one query per row when rendering a list.
_WITH_ITEMS = selectinload(Order.items).selectinload(OrderItem.product)


class OrderRepository:
    """Data access only: no business rules, no HTTP concerns."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, order_id: uuid.UUID, *, for_update: bool = False) -> Order | None:
        """`for_update` takes a row lock until the transaction ends, serialising concurrent
        changes to the same order (a no-op on SQLite, which the unit tests use)."""
        stmt = select(Order).where(Order.id == order_id).options(_WITH_ITEMS)
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def get_by_idempotency_key(self, user_id: uuid.UUID, key: str) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id, Order.idempotency_key == key)
            .options(_WITH_ITEMS)
        )
        return self.db.scalar(stmt)

    def list(
        self,
        *,
        user_id: uuid.UUID | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Order], int]:
        """`user_id=None` means all users (admin view)."""
        conditions = []
        if user_id is not None:
            conditions.append(Order.user_id == user_id)
        if status is not None:
            conditions.append(Order.status == status)

        total = self.db.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
        stmt = (
            select(Order)
            .where(*conditions)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(limit)
            .offset(offset)
            .options(_WITH_ITEMS)
        )
        return self.db.scalars(stmt).all(), total

    def add(self, order: Order) -> None:
        self.db.add(order)

    def add_outbox_event(
        self, *, aggregate_id: uuid.UUID, event_type: str, payload: dict
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type="order",
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        return event
