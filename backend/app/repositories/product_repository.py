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

    def get_many(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Product]:
        if not product_ids:
            return {}
        rows = self.db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        return {product.id: product for product in rows}
