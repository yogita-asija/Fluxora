import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    """Data access only: no business rules, no HTTP concerns."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, limit: int, offset: int) -> Sequence[Product]:
        stmt = select(Product).order_by(Product.name).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    def get(self, product_id: uuid.UUID) -> Product | None:
        return self.db.get(Product, product_id)
