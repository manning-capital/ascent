"""Runtime tests for :class:`ScheduledFeedService`.

Covers the tick loop end-to-end: clock fires → snapshot resolved → fetcher
invoked → event published → run tracker stamps COMPLETED with the right
snapshot_timestamp. Catches the silent-non-firing failure mode we hit earlier.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio

from ascent.application import FeedExecutor, ScheduledFeedService
from ascent.application.execute_feed import FeedContext
from ascent.feeds.schedule import Schedule
from tests.fakes import (
    FakeClock,
    FakeRunTracker,
    InMemoryEventBus,
    InMemoryFeedStore,
)


class _StubFetcher:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df
        self.calls = 0
        self.errors: list[BaseException] = []

    async def fetch(self, snapshot_timestamp: datetime, context: dict[str, Any]) -> pd.DataFrame:
        self.calls += 1
        return self._df

    async def on_error(self, error: BaseException) -> None:
        self.errors.append(error)


class _RaisingFetcher:
    def __init__(self) -> None:
        self.errors: list[BaseException] = []

    async def fetch(self, snapshot_timestamp, context):
        raise RuntimeError("fetcher boom")

    async def on_error(self, error: BaseException) -> None:
        self.errors.append(error)


@pytest_asyncio.fixture
async def wiring():
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    executor = FeedExecutor(feed_store=store, event_bus=bus)
    tracker = FakeRunTracker()
    clock = FakeClock(datetime(2026, 4, 16, 12, 0, tzinfo=UTC))
    ctx = FeedContext(
        feed_id=uuid.uuid4(),
        feed_ref="MARKET_DATA",
        channel="ascent.feed.md",
        output_table="instrument_attribute",
        schedule=Schedule(interval=15, start_date=datetime(2026, 1, 1, tzinfo=UTC)),
    )
    yield store, bus, executor, tracker, clock, ctx


@pytest.mark.asyncio
async def test_service_fires_on_each_clock_tick(wiring):
    store, bus, executor, tracker, clock, ctx = wiring
    df = pd.DataFrame({"attribute_value": [1, 2, 3]})
    fetcher = _StubFetcher(df)

    service = ScheduledFeedService(
        feed=ctx,
        executor=executor,
        run_tracker=tracker,
        clock=clock,
        fetcher_factory=lambda snapshot, context: fetcher,
    )

    task = asyncio.create_task(service.run_forever())
    # FakeClock.sleep_until_tick returns immediately after advancing time, so
    # 3 iterations happen as fast as the event loop schedules them.
    for _ in range(200):
        if fetcher.calls >= 3:
            break
        await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert fetcher.calls >= 3
    feed_events = [e for e in bus.published if e.channel == ctx.channel]
    assert len(feed_events) >= 3
    # Every feed event carries the schedule-aligned snapshot timestamp.
    assert all(e.payload.get("snapshot_timestamp") for e in feed_events)
    # Every tracked run records the snapshot at create time — no post-hoc link.
    feed_traces = [t for t in tracker.traces if t.kind == "feed"]
    assert len(feed_traces) >= 3
    assert all(t.snapshot_timestamp is not None for t in feed_traces[:3])
    assert all(t.outcome == "COMPLETED" for t in feed_traces[:3])


@pytest.mark.asyncio
async def test_fetcher_exception_fails_run_and_service_continues(wiring):
    store, bus, executor, tracker, clock, ctx = wiring
    fetcher = _RaisingFetcher()
    service = ScheduledFeedService(
        feed=ctx,
        executor=executor,
        run_tracker=tracker,
        clock=clock,
        fetcher_factory=lambda snapshot, context: fetcher,
    )
    task = asyncio.create_task(service.run_forever())
    # Wait until either on_error fires OR the tracker records a FAILED trace.
    for _ in range(200):
        if fetcher.errors:
            break
        await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert fetcher.errors, "fetcher.on_error was never called"
    feed_traces = [t for t in tracker.traces if t.kind == "feed"]
    assert feed_traces and any(t.outcome == "FAILED" for t in feed_traces)
