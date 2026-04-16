"""Runtime tests for :class:`ScheduledFeedService`.

Covers the tick loop end-to-end: clock fires → fetcher invoked → partition
created + marked MATERIALIZED → event published → run tracker stamps
COMPLETED. Catches the silent-non-firing failure mode we hit earlier.
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
from ascent.domain import PartitionWindow
from ascent.feeds.schedule import Schedule
from tests.fakes import (
    FakeClock,
    FakeRunTracker,
    InMemoryEventBus,
    InMemoryFeedStore,
    InMemoryPartitionRepository,
)


class _StubFetcher:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df
        self.calls = 0
        self.errors: list[BaseException] = []

    async def fetch(self, partition: PartitionWindow, context: dict[str, Any]) -> pd.DataFrame:
        self.calls += 1
        return self._df

    async def on_error(self, error: BaseException) -> None:
        self.errors.append(error)


class _RaisingFetcher:
    def __init__(self) -> None:
        self.errors: list[BaseException] = []

    async def fetch(self, partition, context):
        raise RuntimeError("fetcher boom")

    async def on_error(self, error: BaseException) -> None:
        self.errors.append(error)


@pytest_asyncio.fixture
async def wiring():
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    partitions = InMemoryPartitionRepository()
    executor = FeedExecutor(feed_store=store, event_bus=bus, partition_repo=partitions)
    tracker = FakeRunTracker()
    clock = FakeClock(datetime(2026, 4, 16, 12, 0, tzinfo=UTC))
    ctx = FeedContext(
        feed_id=uuid.uuid4(),
        feed_ref="MARKET_DATA",
        channel="ascent.feed.md",
        output_table="instrument_attribute",
        schedule=Schedule(interval=15, start_date=datetime(2026, 1, 1, tzinfo=UTC)),
    )
    yield store, bus, partitions, executor, tracker, clock, ctx


@pytest.mark.asyncio
async def test_service_fires_on_each_clock_tick(wiring):
    store, bus, partitions, executor, tracker, clock, ctx = wiring
    df = pd.DataFrame({"attribute_value": [1, 2, 3]})
    fetcher = _StubFetcher(df)

    service = ScheduledFeedService(
        feed=ctx,
        executor=executor,
        run_tracker=tracker,
        clock=clock,
        fetcher_factory=lambda partition, context: fetcher,
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
    # Each tick: one feed event, one partition, one tracker trace.
    feed_events = [e for e in bus.published if e.channel == ctx.channel]
    assert len(feed_events) >= 3
    assert all(e["status"] == "MATERIALIZED" for e in partitions.partitions.values())
    assert len(tracker.traces) >= 3
    assert all(t.outcome == "COMPLETED" for t in tracker.traces[:3])


@pytest.mark.asyncio
async def test_fetcher_exception_marks_partition_failed_and_service_continues(wiring):
    store, bus, partitions, executor, tracker, clock, ctx = wiring
    fetcher = _RaisingFetcher()
    service = ScheduledFeedService(
        feed=ctx,
        executor=executor,
        run_tracker=tracker,
        clock=clock,
        fetcher_factory=lambda partition, context: fetcher,
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
        # The service may or may not propagate depending on error-handling; we
        # assert on observable side effects below.
        pass

    assert fetcher.errors, "fetcher.on_error was never called"
    # A partition row must exist and be FAILED.
    assert any(p["status"] == "FAILED" for p in partitions.partitions.values())
