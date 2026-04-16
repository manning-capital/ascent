"""Clock port — abstracts ``datetime.now`` + schedule ticking for testability."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ascent.feeds.schedule import Schedule


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...

    async def sleep_until_tick(self, schedule: Schedule) -> datetime:
        """Sleep until the next aligned tick of ``schedule``. Returns the tick time."""
        ...
