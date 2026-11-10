"""Race conditions. These need a real database (row locks, unique constraints under
concurrent transactions), so they run only when TEST_DATABASE_URL points at PostgreSQL."""

import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import Order, OutboxEvent, User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderItemCreate
from app.services.order_service import OrderService
from tests.conftest import requires_postgres

THREADS = 8


def run_concurrently(engine, work):
    """Runs work(service, index) in THREADS threads at once, each with its own session."""
    barrier = threading.Barrier(THREADS)

    def worker(index):
        with Session(engine, expire_on_commit=False) as session:
            service = OrderService(session, OrderRepository(session), ProductRepository(session))
            barrier.wait()  # release all threads together to maximise the race
            try:
                return work(service, session, index)
            except Exception as exc:  # collected, not raised, so the test can inspect them
                return exc

    with ThreadPoolExecutor(THREADS) as pool:
        return list(pool.map(worker, range(THREADS)))


@requires_postgres
def test_concurrent_requests_with_the_same_key_create_exactly_one_order(
    engine, db, customer, make_product
):
    product = make_product()
    items = [OrderItemCreate(product_id=product.id, quantity=2)]

    def work(service, session, _):
        user = session.get(User, customer.id)
        return service.create_order(user=user, items=items, idempotency_key="race-key-0001")

    results = run_concurrently(engine, work)

    errors = [r for r in results if isinstance(r, Exception)]
    assert errors == []
    assert sum(1 for _, created in results if created) == 1  # exactly one winner
    assert len({order.id for order, _ in results}) == 1  # everyone got the same order
    db.expire_all()
    assert len(db.scalars(select(Order)).all()) == 1
    assert len(db.scalars(select(OutboxEvent)).all()) == 1


@requires_postgres
def test_concurrent_cancels_succeed_once_and_emit_one_event(engine, db, customer, make_product):
    product = make_product()
    with Session(engine, expire_on_commit=False) as session:
        user = session.get(User, customer.id)
        service = OrderService(session, OrderRepository(session), ProductRepository(session))
        order, _ = service.create_order(
            user=user,
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
            idempotency_key="cancel-race-0001",
        )

    def work(service, session, _):
        user = session.get(User, customer.id)
        return service.cancel_order(user=user, order_id=order.id)

    results = run_concurrently(engine, work)

    winners = [r for r in results if isinstance(r, Order)]
    losers = [r for r in results if isinstance(r, ConflictError)]
    assert len(winners) == 1
    assert len(losers) == THREADS - 1
    db.expire_all()
    events = [e.event_type for e in db.scalars(select(OutboxEvent))]
    assert sorted(events) == ["order.cancelled", "order.created"]
