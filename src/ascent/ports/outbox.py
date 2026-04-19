"""OutboxPublisher port — durable, transactional event publication.

Unlike :class:`EventBus` (best-effort Redis pub/sub), the outbox **requires**
a session because the guarantee is that the business write and the outbox
row commit in the same DB transaction. No session → no transactional
guarantee → no outbox.

A separate relay process reads committed outbox rows and forwards them to
the durable broker (NATS JetStream). See
``docs/durable-messaging-and-plugin-contracts.md``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OutboxPublisher(Protocol):
    """Enqueue a durable event within the caller's transaction.

    ``session`` is the opaque handle from a :class:`UnitOfWork`. The
    enqueue writes into the event-outbox table on that session but does
    **not** commit — the UoW commits. If the UoW rolls back, the enqueue
    rolls back with it, and the event was never emitted.
    """

    async def enqueue(
        self,
        session: Any,
        *,
        channel: str,
        subject: str,
        payload: dict[str, Any],
    ) -> None: ...
