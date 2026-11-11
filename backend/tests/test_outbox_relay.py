import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import OutboxEvent
from app.services.outbox_relay import OutboxRelay, backoff_seconds, topic_for

from tests.conftest import TEST_DATABASE_URL, auth_headers, requires_postgres

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class FakePublisher:
    """Records what was sent; `fail` maps event_id -> error text for events that should fail."""

    def __init__(self, fail=None, delay=0.0):
        self.fail = fail or {}
        self.delay = delay
        self.sent = []
        self._lock = threading.Lock()

    def publish_batch(self, messages):
        if self.delay:
            time.sleep(self.delay)
        out = {}
        for m in messages:
            out[m.event_id] = self.fail.get(m.event_id)
            if out[m.event_id] is None:
                with self._lock:
                    self.sent.append(m)
        return out


class ExplodingPublisher:
    def publish_batch(self, messages):
        raise RuntimeError("broker on fire")


@pytest.fixture()
def settings():
    return get_settings().model_copy(
        update={
            "outbox_batch_size": 50,
            "outbox_max_attempts": 3,
            "outbox_backoff_base_seconds": 10.0,
            "outbox_backoff_max_seconds": 100.0,
        }
    )


@pytest.fixture()
def add_event(db):
    def _add(aggregate_id=None, event_type="order.created", age_seconds=0, payload=None):
        event = OutboxEvent(
            aggregate_type="order",
            aggregate_id=aggregate_id or uuid.uuid4(),
            event_type=event_type,
            payload=payload or {"hello": "world"},
            created_at=BASE + timedelta(seconds=age_seconds),
            available_at=BASE,
        )
        db.add(event)
        db.commit()
        return event

    return _add


def relay(db, publisher, settings):
    return OutboxRelay(db, publisher, settings)


def test_publishes_pending_event_with_envelope_key_and_headers(db, add_event, settings):
    aggregate = uuid.uuid4()
    event = add_event(aggregate, payload={"total_amount": "10.00"})
    publisher = FakePublisher()

    result = relay(db, publisher, settings).run_once(now=BASE + timedelta(seconds=2))

    assert (result.published, result.retried, result.failed) == (1, 0, 0)
    db.refresh(event)
    assert event.status == "published" and event.attempts == 1 and event.published_at is not None
    (message,) = publisher.sent
    assert message.topic == "orderflow.order.events" == topic_for(settings, "order")
    assert message.key == str(aggregate)  # same order -> same Kafka partition
    assert message.headers["event_id"] == str(event.id)
    assert message.headers["event_type"] == "order.created"
    body = json.loads(message.value)
    assert body["event_id"] == str(event.id)
    assert body["aggregate_id"] == str(aggregate)
    assert body["payload"] == {"total_amount": "10.00"}
    assert result.lags_seconds == (2.0,)


def test_nothing_to_do_returns_empty_result(db, settings):
    assert relay(db, FakePublisher(), settings).run_once(now=BASE).claimed == 0


def test_published_events_are_not_published_again(db, add_event, settings):
    add_event()
    publisher = FakePublisher()
    r = relay(db, publisher, settings)
    r.run_once(now=BASE)
    r.run_once(now=BASE + timedelta(minutes=5))
    assert len(publisher.sent) == 1


def test_failure_schedules_retry_with_backoff(db, add_event, settings):
    event = add_event()
    publisher = FakePublisher(fail={str(event.id): "broker unavailable"})
    r = relay(db, publisher, settings)

    result = r.run_once(now=BASE)
    assert (result.published, result.retried) == (0, 1)
    db.refresh(event)
    assert event.status == "pending" and event.attempts == 1
    assert event.last_error == "broker unavailable"
    delay = (event.available_at.replace(tzinfo=UTC) - BASE).total_seconds()
    assert 8 <= delay <= 12  # base 10s, +-20% jitter

    # Not retried while backing off ...
    assert r.run_once(now=BASE + timedelta(seconds=1)).claimed == 0
    # ... but retried once the delay has passed, and success clears the error.
    publisher.fail.clear()
    assert r.run_once(now=BASE + timedelta(seconds=13)).published == 1
    db.refresh(event)
    assert event.status == "published" and event.attempts == 2 and event.last_error is None


def test_event_becomes_failed_after_max_attempts_and_can_be_requeued(db, add_event, settings):
    event = add_event()
    publisher = FakePublisher(fail={str(event.id): "boom"})
    r = relay(db, publisher, settings)
    now = BASE
    results = []
    for _ in range(3):
        results.append(r.run_once(now=now))
        now += timedelta(minutes=10)
    assert [x.retried for x in results] == [1, 1, 0]
    assert results[-1].failed == 1
    db.refresh(event)
    assert event.status == "failed" and event.attempts == 3 and event.last_error == "boom"

    assert r.run_once(now=now + timedelta(days=1)).claimed == 0  # failed events are left alone

    publisher.fail.clear()
    assert r.requeue_failed() == 1
    db.refresh(event)
    assert event.status == "pending" and event.attempts == 0
    assert r.run_once(now=datetime.now(UTC) + timedelta(seconds=5)).published == 1


def test_partial_failure_only_retries_the_failed_event(db, add_event, settings):
    good, bad = add_event(age_seconds=0), add_event(age_seconds=1)
    publisher = FakePublisher(fail={str(bad.id): "nope"})
    result = relay(db, publisher, settings).run_once(now=BASE)
    assert (result.published, result.retried) == (1, 1)
    db.refresh(good), db.refresh(bad)
    assert good.status == "published" and bad.status == "pending"


def test_publisher_crash_never_loses_events(db, add_event, settings):
    event = add_event()
    result = relay(db, ExplodingPublisher(), settings).run_once(now=BASE)
    assert result.retried == 1
    db.refresh(event)
    assert event.status == "pending" and "broker on fire" in event.last_error


def test_missing_acknowledgement_counts_as_failure(db, add_event, settings):
    class Silent:
        def publish_batch(self, messages):
            return {}

    event = add_event()
    assert relay(db, Silent(), settings).run_once(now=BASE).retried == 1
    db.refresh(event)
    assert event.status == "pending" and "no acknowledgement" in event.last_error


def test_batch_size_is_respected_and_oldest_go_first(db, add_event, settings):
    events = [add_event(age_seconds=i) for i in range(5)]
    small = settings.model_copy(update={"outbox_batch_size": 2})
    publisher = FakePublisher()
    relay(db, publisher, small).run_once(now=BASE + timedelta(minutes=1))
    assert [m.event_id for m in publisher.sent] == [str(events[0].id), str(events[1].id)]


def test_events_of_one_order_are_published_in_order(db, add_event, settings):
    aggregate = uuid.uuid4()
    created = add_event(aggregate, "order.created", age_seconds=0)
    cancelled = add_event(aggregate, "order.cancelled", age_seconds=5)
    other = add_event(uuid.uuid4(), "order.created", age_seconds=6)
    publisher = FakePublisher(fail={str(created.id): "down"})
    r = relay(db, publisher, settings)
    now = BASE + timedelta(minutes=1)

    # The first event fails: the later event of the same order must NOT overtake it,
    # while other orders are unaffected.
    r.run_once(now=now)
    assert [m.event_id for m in publisher.sent] == [str(other.id)]
    db.refresh(cancelled)
    assert cancelled.status == "pending"

    # Once it succeeds, the next event of that order follows.
    publisher.fail.clear()
    r.run_once(now=now + timedelta(minutes=1))
    r.run_once(now=now + timedelta(minutes=1))
    assert [m.event_id for m in publisher.sent][1:] == [str(created.id), str(cancelled.id)]


def test_a_failed_event_blocks_later_events_of_the_same_order(db, add_event, settings):
    aggregate = uuid.uuid4()
    first = add_event(aggregate, age_seconds=0)
    second = add_event(aggregate, "order.cancelled", age_seconds=1)
    publisher = FakePublisher(fail={str(first.id): "x"})
    r = relay(db, publisher, settings)
    now = BASE
    for _ in range(3):
        r.run_once(now=now)
        now += timedelta(minutes=10)
    db.refresh(first), db.refresh(second)
    assert first.status == "failed" and second.status == "pending" and second.attempts == 0


def test_backoff_grows_exponentially_and_is_capped(settings):
    def mid(attempt):  # jitter is +-20%, so check the envelope
        return [backoff_seconds(settings, attempt) for _ in range(50)]

    assert all(8 <= d <= 12 for d in mid(1))
    assert all(16 <= d <= 24 for d in mid(2))
    assert all(d <= 120 for d in mid(20))  # cap 100s + jitter


# ------------------------------------------------------------------ with the real API


def test_order_flow_end_to_end_through_the_relay(client, db, customer, make_product, settings):
    product = make_product(stock=10)
    headers = auth_headers(customer)
    created = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": str(product.id), "quantity": 2}]},
        headers={**headers, "Idempotency-Key": "relay-e2e-key-1"},
    ).json()
    cancelled = client.post(f"/api/v1/orders/{created['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200

    # SQLite's CURRENT_TIMESTAMP has one-second resolution; PostgreSQL's does not tie.
    for i, event in enumerate(db.scalars(select(OutboxEvent).order_by(OutboxEvent.event_type))):
        event.created_at = BASE + timedelta(seconds=-i)  # "order.cancelled" sorts first -> later
    db.commit()

    publisher = FakePublisher()
    r = relay(db, publisher, settings)
    now = datetime.now(UTC) + timedelta(seconds=1)
    r.run_once(now=now)
    r.run_once(now=now)  # the second event of an order is released by the next poll

    bodies = [json.loads(m.value) for m in publisher.sent]
    assert [b["event_type"] for b in bodies] == ["order.created", "order.cancelled"]
    assert all(b["aggregate_id"] == created["id"] for b in bodies)
    assert bodies[0]["payload"]["items"][0]["quantity"] == 2
    assert {m.key for m in publisher.sent} == {created["id"]}


# ------------------------------------------------------------------ admin endpoint


def test_admin_outbox_stats_requires_admin(client, customer, admin):
    assert client.get("/api/v1/admin/outbox").status_code == 401
    assert client.get("/api/v1/admin/outbox", headers=auth_headers(customer)).status_code == 403
    assert client.get("/api/v1/admin/outbox", headers=auth_headers(admin)).status_code == 200


def test_admin_outbox_stats_reports_backlog_and_failures(client, db, admin, add_event, settings):
    ok, bad = add_event(age_seconds=0), add_event(age_seconds=1)
    add_event(age_seconds=2)
    publisher = FakePublisher(fail={str(bad.id): "kafka down"})
    r = relay(db, publisher, settings)
    now = BASE
    for _ in range(3):
        r.run_once(now=now)
        now += timedelta(minutes=10)

    data = client.get("/api/v1/admin/outbox", headers=auth_headers(admin)).json()
    assert (data["published"], data["failed"], data["pending"]) == (2, 1, 0)
    assert data["recent_failed"][0]["id"] == str(bad.id)
    assert data["recent_failed"][0]["last_error"] == "kafka down"
    assert data["oldest_pending_age_seconds"] == 0


# ------------------------------------------------------------------ real Kafka client


def test_kafka_publisher_reports_failure_when_broker_is_unreachable(settings):
    pytest.importorskip("confluent_kafka")
    from app.core.config import Settings  # noqa: F401
    from app.services.outbox_relay import OutboundMessage
    from app.workers.publisher import KafkaPublisher

    unreachable = settings.model_copy(
        update={"kafka_bootstrap_servers": "127.0.0.1:1", "outbox_publish_timeout_seconds": 1.5}
    )
    publisher = KafkaPublisher(unreachable)
    message = OutboundMessage("e1", "orderflow.order.events", "k", b"{}", {"event_id": "e1"})
    outcomes = publisher.publish_batch([message])
    assert outcomes["e1"] is not None  # failed (timeout) -> the relay would retry it


def test_ensure_topics_tolerates_existing_topics_but_raises_other_errors(settings, monkeypatch):
    ck = pytest.importorskip("confluent_kafka")
    from concurrent.futures import Future

    from confluent_kafka.admin import AdminClient

    from app.workers.publisher import KafkaPublisher

    def fake_create(code):
        def create_topics(self, new_topics, **kwargs):
            futures = {}
            for topic in new_topics:
                future = Future()
                future.set_exception(ck.KafkaException(ck.KafkaError(code)))
                futures[topic.topic] = future
            return futures

        return create_topics

    publisher = KafkaPublisher(settings.model_copy(update={"kafka_bootstrap_servers": "127.0.0.1:1"}))
    monkeypatch.setattr(AdminClient, "create_topics", fake_create(ck.KafkaError.TOPIC_ALREADY_EXISTS))
    publisher.ensure_topics(["orderflow.order.events"])  # existing topic is fine
    monkeypatch.setattr(AdminClient, "create_topics", fake_create(ck.KafkaError._TRANSPORT))
    with pytest.raises(ck.KafkaException):
        publisher.ensure_topics(["orderflow.order.events"])


# ------------------------------------------------------------------ PostgreSQL only


@requires_postgres
def test_concurrent_relays_never_publish_the_same_event_twice(engine):
    total = 60
    with Session(engine) as s:
        for i in range(total):
            s.add(
                OutboxEvent(
                    aggregate_type="order", aggregate_id=uuid.uuid4(), event_type="order.created",
                    payload={"i": i}, created_at=BASE + timedelta(milliseconds=i), available_at=BASE,
                )
            )
        s.commit()

    publisher = FakePublisher(delay=0.05)  # slow broker -> locks are held, workers overlap
    small = get_settings().model_copy(update={"outbox_batch_size": 7})

    def worker():
        while True:
            with Session(engine) as session:
                if OutboxRelay(session, publisher, small).run_once(now=BASE + timedelta(hours=1)).claimed == 0:
                    return

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    ids = [m.event_id for m in publisher.sent]
    assert len(ids) == total and len(set(ids)) == total  # nothing lost, nothing duplicated
    with Session(engine) as s:
        assert s.scalar(select(func.count()).where(OutboxEvent.status == "published")) == total
