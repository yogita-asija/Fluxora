from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price >= 0", name="price_non_negative"),)

    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    inventory: Mapped["Inventory | None"] = relationship(  # noqa: F821
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
