from sqlalchemy import CheckConstraint, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_values
from app.models.enums import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(in_values("role", UserRole), name="role_valid"),)

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default=UserRole.CUSTOMER.value, server_default=UserRole.CUSTOMER.value
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    orders: Mapped[list["Order"]] = relationship(back_populates="user")  # noqa: F821
