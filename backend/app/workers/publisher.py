"""Kafka implementation of the relay's Publisher, built on confluent-kafka (librdkafka)."""
import logging

from app.core.config import Settings
from app.services.outbox_relay import OutboundMessage

logger = logging.getLogger(__name__)


class KafkaPublisher:
    def __init__(self, settings: Settings) -> None:
        if not settings.kafka_bootstrap_servers:
            raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS is not set")
        from confluent_kafka import Producer  # imported here so the API never needs it

        self.settings = settings
        self._admin = None
        self.timeout = settings.outbox_publish_timeout_seconds
        self.producer = Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "client.id": "orderflow-outbox-relay",
                # Idempotent producer: broker-side dedupe of retries, ordering per partition,
                # and acks=all, so an acknowledged event is not lost if a broker fails.
                "enable.idempotence": True,
                "acks": "all",
                "linger.ms": 5,
                "message.timeout.ms": int(self.timeout * 1000),
                "socket.timeout.ms": int(self.timeout * 1000),
            }
        )

    def ensure_topics(self, topics: list[str]) -> None:
        """Create topics that do not exist yet (idempotent). Replication factor 1 suits the
        single-broker development setup; raise it for a real cluster."""
        from confluent_kafka import KafkaError, KafkaException
        from confluent_kafka.admin import AdminClient, NewTopic

        if self._admin is None:  # one client for all retries (each client owns threads)
            self._admin = AdminClient({"bootstrap.servers": self.settings.kafka_bootstrap_servers})
        futures = self._admin.create_topics(
            [
                NewTopic(topic, num_partitions=self.settings.outbox_topic_partitions, replication_factor=1)
                for topic in topics
            ],
            request_timeout=self.timeout,
        )
        for topic, future in futures.items():
            try:
                future.result()
                logger.info("created Kafka topic %s", topic)
            except KafkaException as exc:
                if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                    raise

    def check_connection(self) -> None:
        """Raises if the broker cannot be reached."""
        self.producer.list_topics(timeout=self.timeout)

    def publish_batch(self, messages: list[OutboundMessage]) -> dict[str, str | None]:
        outcomes: dict[str, str | None] = {}

        def on_delivery(event_id: str):
            def callback(err, _msg) -> None:
                outcomes[event_id] = None if err is None else str(err)

            return callback

        for message in messages:
            try:
                self.producer.produce(
                    message.topic,
                    key=message.key.encode(),
                    value=message.value,
                    headers=list(message.headers.items()),
                    on_delivery=on_delivery(message.event_id),
                )
            except (BufferError, Exception) as exc:  # local queue full, bad topic name, ...
                outcomes[message.event_id] = f"produce failed: {exc}"
        self.producer.flush(self.timeout)
        # Anything still unacknowledged after the timeout counts as a failure and is retried.
        # (The message may still reach Kafka later; that is the duplicate that idempotent
        # consumers absorb.)
        for message in messages:
            outcomes.setdefault(message.event_id, "delivery timed out")
        return outcomes
