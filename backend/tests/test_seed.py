from sqlalchemy import func, select

from app.core.security import UNUSABLE_PASSWORD, verify_password
from app.models import Inventory, Order, Product, User
from app.seed import ADMIN_EMAIL, CUSTOMER_EMAIL, seed

PASSWORDS = {ADMIN_EMAIL: "admin-password-123", CUSTOMER_EMAIL: "customer-password-123"}


def test_seed_populates_demo_data(db):
    counts = seed(db, PASSWORDS)

    assert counts == {"users": 2, "products": 8, "orders": 3}
    assert db.scalar(select(func.count()).select_from(Inventory)) == 8


def test_seed_is_idempotent(db):
    first = seed(db, PASSWORDS)
    second = seed(db, PASSWORDS)

    assert first == second
    assert db.scalar(select(func.count()).select_from(Product)) == 8
    assert db.scalar(select(func.count()).select_from(Order)) == 3


def test_seeded_order_totals_match_their_items(db):
    seed(db, PASSWORDS)

    for order in db.scalars(select(Order)):
        assert order.total_amount == sum(i.unit_price * i.quantity for i in order.items)


def test_seeded_users_can_authenticate_with_the_given_passwords(db):
    seed(db, PASSWORDS)

    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    customer = db.scalar(select(User).where(User.email == CUSTOMER_EMAIL))
    assert admin.role == "admin" and customer.role == "customer"
    assert verify_password(PASSWORDS[ADMIN_EMAIL], admin.password_hash)
    assert not verify_password(PASSWORDS[ADMIN_EMAIL], customer.password_hash)


def test_seed_generates_and_reports_passwords_when_none_given(db):
    generated = {}
    seed(db, {}, generated)

    assert set(generated) == {ADMIN_EMAIL, CUSTOMER_EMAIL}
    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    assert verify_password(generated[ADMIN_EMAIL], admin.password_hash)


def test_rerunning_seed_never_resets_an_existing_password(db):
    seed(db, PASSWORDS)
    seed(db, {ADMIN_EMAIL: "a-completely-different-1"})

    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    assert verify_password(PASSWORDS[ADMIN_EMAIL], admin.password_hash)


def test_seed_sets_a_password_on_accounts_from_before_auth_existed(db):
    seed(db, PASSWORDS)
    legacy = db.scalar(select(User).where(User.email == CUSTOMER_EMAIL))
    legacy.password_hash = UNUSABLE_PASSWORD  # what migration 0002 gives pre-existing users
    db.commit()

    seed(db, {CUSTOMER_EMAIL: "brand-new-password-1"})

    db.refresh(legacy)
    assert verify_password("brand-new-password-1", legacy.password_hash)
