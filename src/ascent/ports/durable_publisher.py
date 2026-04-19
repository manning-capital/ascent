"""DurablePublisher port — outbox relay's interface to the durable broker.

The relay reads outbox rows and calls ``publish`` to forward them. The
broker must provide message-id deduplication so that if the relay crashes
after publishing but before marking the row published, a re-publish is a
no-op rather than a duplicate delivery.

Two implementations are planned:
- :class:`RedisDurablePublisher` (phase-4 shim) forwards to Redis pub/sub
  so existing ``ExchangeService`` subscribers keep working while the
  JetStream stack is built out.
- :class:`NatsJetStreamPublisher` is the production target; uses
  ``Nats-Msg-Id`` for broker-side dedup.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DurablePublisher(Protocol):
    """Broker-agnostic durable publish.

    ``msg_id`` MUST be stable across re-publishes of the same logical event
    so the broker can deduplicate. The outbox row's ``id`` is the canonical
    choice; relays pass ``str(row.id)`` here.
    """

    async def publish(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        msg_id: str,
    ) -> None: ...
