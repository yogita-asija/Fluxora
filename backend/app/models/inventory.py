import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Inventory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stock level for one product. `version` enables optimistic locking on updates."""

    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="reserved_within_on_hand"),
        CheckConstraint("reorder_level >= 0", name="reorder_level_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reorder_level: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)

    product: Mapped["Product"] = relationship(back_populates="inventory")  # noqa: F821

    __mapper_args__ = {"version_id_col": version}

    @property
    def quantity_available(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved
