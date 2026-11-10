import os
import secrets

# Must be set before `app` is imported: settings are read at import time.
# By default tests run on in-memory SQLite, so no database server is needed.
# Set TEST_DATABASE_URL to run the same suite on PostgreSQL (needed for the concurrency tests).
os.environ["DATABASE_URL"] = "sqlite+pysqlite://"
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)  # random per run, never a fixed secret
os.environ["REDIS_URL"] = ""  # login throttle uses its in-process store
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["ENVIRONMENT"] = "development"

import uuid  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.rate_limit import get_login_throttle  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Inventory, Product, User  # noqa: E402

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
PASSWORD = "correct-horse-battery"
_PASSWORD_HASH = hash_password(PASSWORD)  # hashed once: argon2 is deliberately slow

requires_postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to run PostgreSQL-only tests"
)


@pytest.fixture()
def engine():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine(
            "sqlite+pysqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture(autouse=True)
def fresh_login_throttle():
    get_login_throttle.cache_clear()
    yield
    get_login_throttle.cache_clear()


@pytest.fixture()
def client(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # raise_server_exceptions=False lets us assert on the 500 JSON body.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db):
    def _make(email="user@example.com", role="customer", is_active=True, password=None) -> User:
        user = User(
            email=email,
            full_name="Test User",
            role=role,
            is_active=is_active,
            password_hash=hash_password(password) if password else _PASSWORD_HASH,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture()
def make_product(db):
    def _make(sku=None, name="Test Product", price="12.50", stock=100, is_active=True) -> Product:
        product = Product(
            sku=sku or f"SKU-{uuid.uuid4().hex[:8]}",
            name=name,
            price=Decimal(price),
            is_active=is_active,
        )
        product.inventory = Inventory(quantity_on_hand=stock)
        db.add(product)
        db.commit()
        return product

    return _make


def auth_headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def customer(make_user):
    return make_user("customer@example.com")


@pytest.fixture()
def admin(make_user):
    return make_user("admin@example.com", role="admin")


@pytest.fixture()
def headers(customer):
    return auth_headers(customer)
