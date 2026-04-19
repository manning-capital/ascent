"""DurableConsumer port — at-least-once subscription with explicit acks.

Wraps a durable broker subscription so the dispatcher and fill-handler can
consume without importing NATS directly. Every delivered message carries
an ``ack/nak/term`` contract:

- ``ack()``   — processed successfully; broker advances the cursor.
- ``nak()``   — retry after ``ack_wait``; broker redelivers.
- ``term()``  — poison message; broker moves it to DLQ and never redelivers.

Consumers MUST call exactly one of these per delivered message. Forgetting
to ack means the broker redelivers after its ack-wait timeout — so handlers
should ack on success and explicitly nak on transient failure, not rely on
the timeout as a retry mechanism.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DurableMessage(Protocol):
    subject: str
    payload: dict[str, Any]
    msg_id: str | None

    async def ack(self) -> None: ...

    async def nak(self) -> None: ...

    async def term(self) -> None: ...


class DurableConsumer(Protocol):
    """Async iterator yielding :class:`DurableMessage` until closed.

    Implementations fetch from the broker in pull mode (preferred for
    back-pressure safety). Cancelling the iterator closes the subscription
    cleanly.
    """

    def __aiter__(self) -> AsyncIterator[DurableMessage]: ...

    async def aclose(self) -> None: ...
