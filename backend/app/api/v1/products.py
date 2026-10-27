import uuid

from fastapi import APIRouter, Query

from app.api.deps import ProductServiceDep
from app.schemas.product import ProductRead

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(
    service: ProductServiceDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return service.list_products(limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, service: ProductServiceDep):
    return service.get_product(product_id)
