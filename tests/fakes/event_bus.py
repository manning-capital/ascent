"""Asyncio-native in-memory EventBus fake."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from ascent.ports import Event, EventBus


class InMemoryEventBus(EventBus):
    """Per-channel ``asyncio.Queue`` fan-out. Fits the Redis pub/sub semantics."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[Event]]] = {}
        self.published: list[Event] = []

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        event = Event(channel=channel, payload=payload)
        self.published.append(event)
        for queue in self._subscribers.get(channel, []):
            await queue.put(event)

    def subscribe(self, channels: list[str]) -> AsyncIterator[Event]:
        return _Subscription(self, channels)


class _Subscription:
    def __init__(self, bus: InMemoryEventBus, channels: list[str]) -> None:
        self._bus = bus
        self._channels = channels
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        for channel in channels:
            bus._subscribers.setdefault(channel, []).append(self._queue)

    def __aiter__(self) -> _Subscription:
        return self

    async def __anext__(self) -> Event:
        return await self._queue.get()

    async def aclose(self) -> None:
        for channel in self._channels:
            subs = self._bus._subscribers.get(channel, [])
            if self._queue in subs:
                subs.remove(self._queue)
