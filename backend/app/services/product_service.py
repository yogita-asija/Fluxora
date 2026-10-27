import uuid
from collections.abc import Sequence

from app.core.errors import NotFoundError
from app.models import Product
from app.repositories.product_repository import ProductRepository


class ProductService:
    """Business rules for products. Order, inventory, and payment services follow this shape."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def list_products(self, *, limit: int, offset: int) -> Sequence[Product]:
        return self.repository.list(limit=limit, offset=offset)

    def get_product(self, product_id: uuid.UUID) -> Product:
        product = self.repository.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product
