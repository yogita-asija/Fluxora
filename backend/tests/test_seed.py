from sqlalchemy import func, select

from app.models import Inventory, Order, Product
from app.seed import seed


def test_seed_populates_demo_data(db):
    counts = seed(db)

    assert counts == {"users": 2, "products": 8, "orders": 3}
    assert db.scalar(select(func.count()).select_from(Inventory)) == 8


def test_seed_is_idempotent(db):
    first = seed(db)
    second = seed(db)

    assert first == second
    assert db.scalar(select(func.count()).select_from(Product)) == 8
    assert db.scalar(select(func.count()).select_from(Order)) == 3


def test_seeded_order_totals_match_their_items(db):
    seed(db)

    for order in db.scalars(select(Order)):
        assert order.total_amount == sum(i.unit_price * i.quantity for i in order.items)
