"""In-memory :class:`DurableConsumer` fake.

Drive tests by calling ``feed`` to push a message; iterate the consumer to
receive it. Each message records whether it was acked/naked/termed so tests
can assert handler behavior.

Usage::

    consumer = FakeDurableConsumer()
    consumer.feed("subject", {"v": 1}, msg_id="1")
    async for msg in consumer:
        assert msg.payload == {"v": 1}
        await msg.ack()
        break
    assert consumer.acked[0].payload == {"v": 1}
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _FakeMessage:
    subject: str
    payload: dict[str, Any]
    msg_id: str | None = None
    _ack_event: asyncio.Event | None = None
    _nak_event: asyncio.Event | None = None
    _term_event: asyncio.Event | None = None
    _acked: bool = False
    _naked: bool = False
    _termed: bool = False

    async def ack(self) -> None:
        self._acked = True
        if self._ack_event is not None:
            self._ack_event.set()

    async def nak(self) -> None:
        self._naked = True
        if self._nak_event is not None:
            self._nak_event.set()

    async def term(self) -> None:
        self._termed = True
        if self._term_event is not None:
            self._term_event.set()


@dataclass
class FakeDurableConsumer:
    """Queue-backed consumer. Tests push via ``feed()`` and iterate to receive."""

    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _closed: bool = False
    delivered: list[_FakeMessage] = field(default_factory=list)

    def feed(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        msg_id: str | None = None,
    ) -> _FakeMessage:
        msg = _FakeMessage(
            subject=subject,
            payload=payload,
            msg_id=msg_id,
            _ack_event=asyncio.Event(),
            _nak_event=asyncio.Event(),
            _term_event=asyncio.Event(),
        )
        self._queue.put_nowait(msg)
        return msg

    @property
    def acked(self) -> list[_FakeMessage]:
        return [m for m in self.delivered if m._acked]

    @property
    def naked(self) -> list[_FakeMessage]:
        return [m for m in self.delivered if m._naked]

    @property
    def termed(self) -> list[_FakeMessage]:
        return [m for m in self.delivered if m._termed]

    def __aiter__(self) -> AsyncIterator[_FakeMessage]:
        return self

    async def __anext__(self) -> _FakeMessage:
        if self._closed and self._queue.empty():
            raise StopAsyncIteration
        msg = await self._queue.get()
        self.delivered.append(msg)
        return msg

    async def aclose(self) -> None:
        self._closed = True
