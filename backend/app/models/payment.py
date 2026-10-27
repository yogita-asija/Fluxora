import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_values
from app.models.enums import PaymentStatus


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_reference", name="uq_payments_provider_reference"),
        CheckConstraint(in_values("status", PaymentStatus), name="status_valid"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    status: Mapped[str] = mapped_column(
        String(32),
        default=PaymentStatus.PENDING.value,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), default="mock", server_default="mock")
    provider_reference: Mapped[str | None] = mapped_column(String(128))

    order: Mapped["Order"] = relationship(back_populates="payments")  # noqa: F821
