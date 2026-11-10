import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_values
from app.models.enums import OrderStatus


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(in_values("status", OrderStatus), name="status_valid"),
        CheckConstraint("total_amount >= 0", name="total_non_negative"),
        # Scoped per user: one customer's key can never collide with, or reveal, another's.
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.PENDING.value,
        server_default=OrderStatus.PENDING.value,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    # Lets clients retry order creation safely: same key (and same request) -> same order.
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    # SHA-256 of the canonical request, to detect a key being reused with a different request.
    request_hash: Mapped[str | None] = mapped_column(String(64))

    user: Mapped["User"] = relationship(back_populates="orders")  # noqa: F821
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")  # noqa: F821
    reservations: Mapped[list["InventoryReservation"]] = relationship(  # noqa: F821
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Price captured at order time so later product price changes don't rewrite history.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
