"""FakeClock — hand-rolled virtual time for deterministic use-case tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from ascent.feeds.schedule import Schedule
from ascent.ports import Clock


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)
        self.ticks: list[datetime] = []

    def now(self) -> datetime:
        return self._now

    def advance(self, *, seconds: float = 0, minutes: float = 0) -> None:
        self._now += timedelta(seconds=seconds, minutes=minutes)

    async def sleep_until_tick(self, schedule: Schedule) -> datetime:
        # Yield real event-loop control. Without this, tick-driven services
        # run in a tight cooperative loop and never let test polling logic
        # run — tests hang. The real SystemClock blocks on a thread so
        # naturally yields; the fake must simulate that.
        await asyncio.sleep(0)
        self._now += timedelta(seconds=schedule.interval)
        self.ticks.append(self._now)
        return self._now
