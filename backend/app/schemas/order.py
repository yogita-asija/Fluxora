import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_ITEMS_PER_ORDER = 50
MAX_QUANTITY_PER_ITEM = 100

# Idempotency keys are client-chosen: keep them short and free of odd characters.
IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{8,128}$"


class OrderItemCreate(BaseModel):
    # Only a product and a quantity are accepted. Prices, totals and status are computed on
    # the server; extra="forbid" turns any attempt to send them into a 422.
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_ITEM)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemCreate] = Field(min_length=1, max_length=MAX_ITEMS_PER_ORDER)

    @field_validator("items")
    @classmethod
    def no_duplicate_products(cls, items: list[OrderItemCreate]) -> list[OrderItemCreate]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("each product may appear only once; combine quantities instead")
        return items


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    total_amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderPage(BaseModel):
    items: list[OrderRead]
    total: int
    limit: int
    offset: int
