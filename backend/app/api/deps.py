from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService

DbSession = Annotated[Session, Depends(get_db)]


def get_product_service(db: DbSession) -> ProductService:
    return ProductService(ProductRepository(db))


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
