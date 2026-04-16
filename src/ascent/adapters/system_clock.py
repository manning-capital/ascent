"""Real-time :class:`ascent.ports.Clock` implementation backed by AlignedTimer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ascent.feeds.schedule import Schedule
from ascent.ports import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(tz=UTC)

    async def sleep_until_tick(self, schedule: Schedule) -> datetime:
        # Lazy import: avoids a package-level cycle between adapters and engine.
        from ascent.engine.timer import AlignedTimer

        timer = AlignedTimer(schedule)
        return await asyncio.to_thread(timer.wait_for_tick)
