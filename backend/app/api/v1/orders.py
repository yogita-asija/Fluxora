import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import CurrentUser, OrderServiceDep
from app.models.enums import OrderStatus
from app.schemas.order import IDEMPOTENCY_KEY_PATTERN, OrderCreate, OrderPage, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        pattern=IDEMPOTENCY_KEY_PATTERN,
        description="Unique key per order attempt (8-128 chars). Retrying with the same key "
        "and body returns the original order instead of creating a duplicate.",
    ),
]


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replay of an earlier request with the same key"}},
)
def create_order(
    payload: OrderCreate,
    idempotency_key: IdempotencyKey,
    user: CurrentUser,
    service: OrderServiceDep,
    response: Response,
):
    order, created = service.create_order(
        user=user, items=payload.items, idempotency_key=idempotency_key
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return order


@router.get("", response_model=OrderPage)
def list_orders(
    user: CurrentUser,
    service: OrderServiceDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    orders, total = service.list_orders(
        user=user,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return OrderPage(items=orders, total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: uuid.UUID, user: CurrentUser, service: OrderServiceDep):
    return service.get_order(user=user, order_id=order_id)


@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_order(order_id: uuid.UUID, user: CurrentUser, service: OrderServiceDep):
    return service.cancel_order(user=user, order_id=order_id)
