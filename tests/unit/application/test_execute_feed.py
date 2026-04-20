"""FeedExecutor use-case tests with in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from ascent.application.execute_feed import FeedContext, FeedExecutor
from ascent.feeds.schedule import Schedule
from tests.fakes import (
    InMemoryEventBus,
    InMemoryFeedStore,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


class _StubFetcher:
    def __init__(self, df: pd.DataFrame, raises: BaseException | None = None) -> None:
        self._df = df
        self._raises = raises
        self.errors: list[BaseException] = []

    async def fetch(self, snapshot_timestamp: datetime, context: dict[str, Any]) -> pd.DataFrame:
        if self._raises:
            raise self._raises
        return self._df

    async def on_error(self, error: BaseException) -> None:
        self.errors.append(error)


@pytest.fixture
def context():
    return FeedContext(
        feed_id=uuid.uuid4(),
        feed_ref="MARKET_DATA",
        channel="ascent.feed.test",
        output_table="instrument_attribute",
        schedule=Schedule(interval=60, start_date=datetime(2026, 1, 1, tzinfo=UTC)),
    )


@pytest.fixture
def wiring():
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    executor = FeedExecutor(feed_store=store, event_bus=bus)
    return store, bus, executor


class TestFeedExecutor:
    @pytest.mark.asyncio
    async def test_happy_path_publishes_and_persists(self, context, wiring):
        store, bus, executor = wiring
        df = pd.DataFrame({"x": [1, 2]})
        feed_run_id = uuid.uuid4()

        snapshot = executor.resolve_snapshot(context, NOW)
        outcome = await executor.execute(
            feed=context,
            tick=NOW,
            snapshot_timestamp=snapshot,
            fetcher=_StubFetcher(df),
            feed_run_id=feed_run_id,
        )

        assert outcome.rows == 2
        assert outcome.snapshot_timestamp == snapshot
        cached = await store.get_latest(context.feed_id)
        assert len(cached) == 2
        assert bus.published[0].channel == context.channel
        payload = bus.published[0].payload
        assert payload["feed_id"] == str(context.feed_id)
        assert payload["snapshot_timestamp"] == snapshot.isoformat()
        assert payload["feed_run_id"] == str(feed_run_id)

    @pytest.mark.asyncio
    async def test_fetch_failure_notifies_feed_and_suppresses_publish(self, context, wiring):
        _, bus, executor = wiring
        fetcher = _StubFetcher(pd.DataFrame(), raises=RuntimeError("boom"))
        snapshot = executor.resolve_snapshot(context, NOW)
        with pytest.raises(RuntimeError, match="boom"):
            await executor.execute(
                feed=context,
                tick=NOW,
                snapshot_timestamp=snapshot,
                fetcher=fetcher,
                feed_run_id=uuid.uuid4(),
            )
        assert fetcher.errors and isinstance(fetcher.errors[0], RuntimeError)
        # Nothing published when fetch fails — no partial state downstream.
        assert bus.published == []

    @pytest.mark.asyncio
    async def test_resolve_snapshot_aligns_tick_to_schedule(self, context, wiring):
        _, _, executor = wiring
        # Tick at 12:00:37 with a 60s schedule anchored to an epoch boundary
        # must snap back to 12:00:00.
        tick = datetime(2026, 4, 16, 12, 0, 37, tzinfo=UTC)
        snapshot = executor.resolve_snapshot(context, tick)
        assert snapshot == datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_resolve_snapshot_returns_tick_when_no_schedule(self, wiring):
        _, _, executor = wiring
        # Triggered feed: no schedule, snapshot is whatever the caller passed.
        ctx_no_schedule = FeedContext(
            feed_id=uuid.uuid4(),
            feed_ref="TRIGGERED",
            channel="ascent.feed.triggered",
            output_table="instrument_attribute",
            schedule=None,
        )
        assert executor.resolve_snapshot(ctx_no_schedule, NOW) == NOW
