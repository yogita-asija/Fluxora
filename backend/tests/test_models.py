import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Inventory,
    InventoryReservation,
    Order,
    OrderItem,
    OutboxEvent,
    ProcessedEvent,
    Product,
    User,
)


@pytest.fixture()
def user(db):
    user = User(email="u@example.com", full_name="U")
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def product(db):
    product = Product(sku="SKU-1", name="Thing", price=Decimal("10.00"))
    product.inventory = Inventory(quantity_on_hand=5)
    db.add(product)
    db.commit()
    return product


def test_defaults_are_applied(db, user, product):
    assert user.role == "customer"
    assert user.is_active is True
    assert product.currency == "USD"
    assert product.inventory.quantity_available == 5


def test_product_sku_is_unique(db, product):
    db.add(Product(sku="SKU-1", name="Duplicate", price=Decimal("1.00")))
    with pytest.raises(IntegrityError):
        db.commit()


def test_negative_price_is_rejected(db):
    db.add(Product(sku="NEG", name="Negative", price=Decimal("-1.00")))
    with pytest.raises(IntegrityError):
        db.commit()


def test_cannot_reserve_more_than_on_hand(db, product):
    product.inventory.quantity_reserved = 6
    with pytest.raises(IntegrityError):
        db.commit()


def test_invalid_order_status_is_rejected(db, user):
    db.add(Order(user_id=user.id, status="teleported", total_amount=Decimal("1.00")))
    with pytest.raises(IntegrityError):
        db.commit()


def test_order_item_quantity_must_be_positive(db, user, product):
    order = Order(user_id=user.id, total_amount=Decimal("0"))
    order.items.append(OrderItem(product_id=product.id, quantity=0, unit_price=Decimal("10.00")))
    db.add(order)
    with pytest.raises(IntegrityError):
        db.commit()


def test_product_appears_once_per_order(db, user, product):
    order = Order(user_id=user.id, total_amount=Decimal("20.00"))
    order.items = [
        OrderItem(product_id=product.id, quantity=1, unit_price=Decimal("10.00")),
        OrderItem(product_id=product.id, quantity=1, unit_price=Decimal("10.00")),
    ]
    db.add(order)
    with pytest.raises(IntegrityError):
        db.commit()


def test_idempotency_key_is_unique(db, user):
    db.add_all(
        [
            Order(user_id=user.id, total_amount=Decimal("1"), idempotency_key="k"),
            Order(user_id=user.id, total_amount=Decimal("1"), idempotency_key="k"),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_order_removes_items_and_reservations(db, user, product):
    order = Order(user_id=user.id, total_amount=Decimal("10.00"))
    order.items.append(OrderItem(product_id=product.id, quantity=1, unit_price=Decimal("10.00")))
    order.reservations.append(InventoryReservation(product_id=product.id, quantity=1))
    db.add(order)
    db.commit()

    db.delete(order)
    db.commit()

    assert db.scalars(select(OrderItem)).all() == []
    assert db.scalars(select(InventoryReservation)).all() == []


def test_processed_event_is_unique_per_consumer(db):
    event_id = uuid.uuid4()
    db.add(ProcessedEvent(event_id=event_id, consumer="inventory"))
    db.add(ProcessedEvent(event_id=event_id, consumer="payments"))  # different consumer: ok
    db.commit()

    db.add(ProcessedEvent(event_id=event_id, consumer="inventory"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_outbox_event_defaults(db):
    event = OutboxEvent(
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        event_type="order.created",
        payload={"order_id": "abc"},
    )
    db.add(event)
    db.commit()

    assert event.status == "pending"
    assert event.attempts == 0
    assert event.payload == {"order_id": "abc"}
