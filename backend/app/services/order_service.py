import hashlib
import json
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    IdempotencyConflictError,
    NotFoundError,
    UnprocessableError,
)
from app.models import Order, OrderItem, User
from app.models.enums import OrderStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderItemCreate


def request_fingerprint(items: Sequence[OrderItemCreate]) -> str:
    """Stable hash of what the client asked for (order of items doesn't matter)."""
    canonical = json.dumps(
        sorted([str(item.product_id), item.quantity] for item in items), separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class OrderService:
    """Order business rules. Every state change commits the order change and its outbox event
    in ONE transaction, so an event exists if and only if the change happened."""

    def __init__(self, db: Session, orders: OrderRepository, products: ProductRepository) -> None:
        self.db = db
        self.orders = orders
        self.products = products

    # ------------------------------------------------------------------ create
    def create_order(
        self, *, user: User, items: Sequence[OrderItemCreate], idempotency_key: str
    ) -> tuple[Order, bool]:
        """Returns (order, created). `created` is False when this is a replay of an earlier
        request with the same Idempotency-Key, in which case nothing is written."""
        fingerprint = request_fingerprint(items)

        existing = self.orders.get_by_idempotency_key(user.id, idempotency_key)
        if existing:
            return self._replay(existing, fingerprint), False

        order = self._build_order(user, items, idempotency_key, fingerprint)
        try:
            self.orders.add(order)
            self.orders.add_outbox_event(
                aggregate_id=order.id,
                event_type="order.created",
                payload=self._created_payload(order),
            )
            self.db.commit()
        except IntegrityError:
            # Two requests with the same key raced; the database's unique constraint let only
            # one through. Roll back and answer with the winner's order.
            self.db.rollback()
            existing = self.orders.get_by_idempotency_key(user.id, idempotency_key)
            if existing is None:
                raise
            return self._replay(existing, fingerprint), False

        return self.orders.get(order.id), True  # re-read: loads server-generated columns

    @staticmethod
    def _replay(existing: Order, fingerprint: str) -> Order:
        if existing.request_hash != fingerprint:
            raise IdempotencyConflictError(
                "This Idempotency-Key was already used with a different request"
            )
        return existing

    def _build_order(
        self, user: User, items: Sequence[OrderItemCreate], key: str, fingerprint: str
    ) -> Order:
        products = self.products.get_many([item.product_id for item in items])

        problems = []
        for item in items:
            product = products.get(item.product_id)
            if product is None:
                problems.append({"product_id": str(item.product_id), "reason": "not_found"})
            elif not product.is_active:
                problems.append({"product_id": str(item.product_id), "reason": "inactive"})
        if problems:
            raise UnprocessableError(
                "Some products are unavailable", details=problems
            )

        currencies = {products[item.product_id].currency for item in items}
        if len(currencies) != 1:
            raise UnprocessableError("All products in an order must use the same currency")

        order = Order(
            id=uuid.uuid4(),
            user_id=user.id,
            status=OrderStatus.PENDING.value,
            currency=currencies.pop(),
            idempotency_key=key,
            request_hash=fingerprint,
            total_amount=Decimal("0"),
        )
        for item in items:
            product = products[item.product_id]
            order.items.append(
                # Price comes from the database, never from the client.
                OrderItem(
                    product_id=product.id, quantity=item.quantity, unit_price=product.price
                )
            )
        order.total_amount = sum(
            (line.unit_price * line.quantity for line in order.items), Decimal("0")
        )
        return order

    @staticmethod
    def _created_payload(order: Order) -> dict:
        return {
            "order_id": str(order.id),
            "user_id": str(order.user_id),
            "currency": order.currency,
            "total_amount": str(order.total_amount),
            "items": [
                {
                    "product_id": str(line.product_id),
                    "quantity": line.quantity,
                    "unit_price": str(line.unit_price),
                }
                for line in order.items
            ],
        }

    # -------------------------------------------------------------------- read
    def list_orders(
        self, *, user: User, status: str | None, limit: int, offset: int
    ) -> tuple[Sequence[Order], int]:
        """Customers see their own orders; admins see everyone's."""
        scope = None if user.is_admin else user.id
        return self.orders.list(user_id=scope, status=status, limit=limit, offset=offset)

    def get_order(self, *, user: User, order_id: uuid.UUID) -> Order:
        order = self.orders.get(order_id)
        return self._visible_or_404(order, user)

    @staticmethod
    def _visible_or_404(order: Order | None, user: User) -> Order:
        # Someone else's order is reported as "not found" rather than "forbidden", so ids
        # can't be probed to learn which orders exist.
        if order is None or (not user.is_admin and order.user_id != user.id):
            raise NotFoundError("Order not found")
        return order

    # ------------------------------------------------------------------ cancel
    def cancel_order(self, *, user: User, order_id: uuid.UUID) -> Order:
        # The row lock makes concurrent cancels (or a cancel racing a later workflow step)
        # run one at a time, so only one can win and only one event is written.
        order = self._visible_or_404(self.orders.get(order_id, for_update=True), user)

        if order.status != OrderStatus.PENDING.value:
            self.db.rollback()  # release the lock
            raise ConflictError(f"A {order.status} order can no longer be cancelled")

        order.status = OrderStatus.CANCELLED.value
        self.orders.add_outbox_event(
            aggregate_id=order.id,
            event_type="order.cancelled",
            payload={
                "order_id": str(order.id),
                "user_id": str(order.user_id),
                "cancelled_by": str(user.id),
            },
        )
        self.db.commit()
        return self.orders.get(order_id)
