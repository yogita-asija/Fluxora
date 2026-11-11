"""Outbox relay worker.  Run with:  python -m app.workers.outbox_relay

    python -m app.workers.outbox_relay                      # run the relay
    python -m app.workers.outbox_relay --requeue-failed     # give failed events fresh attempts
"""
import argparse
import logging
import signal
import threading
import time
import uuid
from datetime import UTC, datetime

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.repositories.outbox_repository import OutboxRepository
from app.services.outbox_relay import BatchResult, OutboxRelay, topic_for

logger = logging.getLogger("outbox_relay")

PUBLISHED = Counter("outbox_events_published_total", "Events acknowledged by Kafka")
RETRIED = Counter("outbox_publish_retries_total", "Publish attempts that failed and were rescheduled")
DEAD = Counter("outbox_events_failed_total", "Events moved to the failed state after max attempts")
LAG = Histogram(
    "outbox_publish_lag_seconds",
    "Time from the event being written to Kafka acknowledging it",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 300),
)
BATCH_SECONDS = Histogram("outbox_batch_duration_seconds", "Time spent processing one batch")
PENDING = Gauge("outbox_pending_events", "Events waiting to be published")
FAILED = Gauge("outbox_failed_events", "Events in the failed state (need attention)")
OLDEST = Gauge("outbox_oldest_pending_age_seconds", "Age of the oldest unpublished event")
STATS_EVERY_SECONDS = 5.0


def record(result: BatchResult, seconds: float) -> None:
    PUBLISHED.inc(result.published)
    RETRIED.inc(result.retried)
    DEAD.inc(result.failed)
    for lag in result.lags_seconds:
        LAG.observe(lag)
    BATCH_SECONDS.observe(seconds)


def refresh_gauges() -> None:
    with SessionLocal() as db:
        stats = OutboxRepository(db).stats(now=datetime.now(UTC))
    PENDING.set(stats["pending"])
    FAILED.set(stats["failed"])
    OLDEST.set(stats["oldest_pending_age_seconds"])


def requeue(event_id: str | None) -> int:
    with SessionLocal() as db:
        return OutboxRelay(db, publisher=None, settings=get_settings()).requeue_failed(  # type: ignore[arg-type]
            uuid.UUID(event_id) if event_id else None
        )


def run(settings: Settings) -> None:
    from app.workers.publisher import KafkaPublisher

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    start_http_server(settings.outbox_metrics_port)
    publisher = KafkaPublisher(settings)
    topics = [topic_for(settings, "order")]
    while not stop.is_set():  # the broker may still be starting: retry instead of crashing
        try:
            publisher.ensure_topics(topics)
            break
        except Exception as exc:
            logger.warning("Kafka not ready (%s); retrying in 3s", exc)
            stop.wait(3)

    if stop.is_set():
        return
    logger.info("outbox relay started (topics=%s, batch=%d)", topics, settings.outbox_batch_size)
    next_stats = 0.0
    while not stop.is_set():
        started = time.monotonic()
        try:
            with SessionLocal() as db:
                result = OutboxRelay(db, publisher, settings).run_once()
            record(result, time.monotonic() - started)
            if result.claimed:
                logger.info(
                    "batch: published=%d retried=%d failed=%d",
                    result.published, result.retried, result.failed,
                )
            if time.monotonic() >= next_stats:
                refresh_gauges()
                next_stats = time.monotonic() + STATS_EVERY_SECONDS
        except Exception:
            logger.exception("relay iteration failed; backing off")
            stop.wait(2)
            continue
        # Keep draining while there is work; sleep only when idle.
        if result.claimed == 0:
            stop.wait(settings.outbox_poll_interval_seconds)
    publisher.producer.flush(5)
    logger.info("outbox relay stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="OrderFlow outbox relay")
    parser.add_argument("--requeue-failed", action="store_true", help="requeue failed events and exit")
    parser.add_argument("--event-id", help="with --requeue-failed: only this event")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    if args.requeue_failed:
        print(f"requeued {requeue(args.event_id)} failed event(s)")
        return
    run(settings)


if __name__ == "__main__":
    main()
