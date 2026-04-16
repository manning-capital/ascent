"""EventBus port — async publish/subscribe notification channel."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Event:
    channel: str
    payload: dict[str, Any]


@runtime_checkable
class EventBus(Protocol):
    """Lightweight notification bus. Replaces the Redis pub/sub usage in EngineCache.

    Contract:
    - ``publish`` returns when the bus has accepted the message; delivery to
      subscribers is at-most-once and may be lossy (consistent with Redis pub/sub).
    - ``subscribe`` yields events until the iterator is closed by the consumer.
    - Closing the iterator must release any underlying subscription.
    """

    async def publish(self, channel: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, channels: list[str]) -> AsyncIterator[Event]: ...
