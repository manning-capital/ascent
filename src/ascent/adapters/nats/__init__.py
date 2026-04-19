"""NATS JetStream adapters.

- :class:`NatsJetStreamPublisher` — durable publisher with ``Nats-Msg-Id`` dedup.
- :class:`NatsJetStreamConsumer` — pull-based durable consumer.
- :func:`ensure_stream` — idempotent stream provisioning.
- :func:`connect_nats` — connection factory; returns a connected ``nats.aio.client.Client``.
"""

from ascent.adapters.nats.jetstream import (
    NatsJetStreamConsumer,
    NatsJetStreamPublisher,
    connect_nats,
    ensure_stream,
)

__all__ = [
    "NatsJetStreamConsumer",
    "NatsJetStreamPublisher",
    "connect_nats",
    "ensure_stream",
]
