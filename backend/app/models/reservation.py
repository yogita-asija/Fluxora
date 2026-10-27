import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_values
from app.models.enums import ReservationStatus


class InventoryReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stock held for an order until payment confirms it or the hold expires."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "product_id", name="uq_inventory_reservations_order_id_product_id"
        ),
        CheckConstraint(in_values("status", ReservationStatus), name="status_valid"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # Supports the "find expired pending holds" sweep.
        Index("ix_inventory_reservations_status_expires_at", "status", "expires_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReservationStatus.PENDING.value,
        server_default=ReservationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship(back_populates="reservations")  # noqa: F821
    product: Mapped["Product"] = relationship()  # noqa: F821
