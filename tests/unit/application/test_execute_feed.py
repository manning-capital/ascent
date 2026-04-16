"""FeedExecutor use-case tests with in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from ascent.application.execute_feed import FeedContext, FeedExecutor
from ascent.domain import PartitionWindow
from ascent.feeds.schedule import Schedule
from tests.fakes import (
    InMemoryEventBus,
    InMemoryFeedStore,
    InMemoryPartitionRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


class _StubFetcher:
    def __init__(self, df: pd.DataFrame, raises: BaseException | None = None) -> None:
        self._df = df
        self._raises = raises
        self.errors: list[BaseException] = []

    async def fetch(self, partition: PartitionWindow, context: dict[str, Any]) -> pd.DataFrame:
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
    partitions = InMemoryPartitionRepository()
    executor = FeedExecutor(feed_store=store, event_bus=bus, partition_repo=partitions)
    return store, bus, partitions, executor


class TestFeedExecutor:
    @pytest.mark.asyncio
    async def test_happy_path_publishes_and_persists(self, context, wiring):
        store, bus, partitions, executor = wiring
        df = pd.DataFrame({"x": [1, 2]})
        feed_run_id = uuid.uuid4()

        outcome = await executor.execute(
            feed=context,
            tick=NOW,
            fetcher=_StubFetcher(df),
            feed_run_id=feed_run_id,
        )

        assert outcome.rows == 2
        cached = await store.get_latest(context.feed_id)
        assert len(cached) == 2
        assert bus.published[0].channel == context.channel
        assert bus.published[0].payload["feed_id"] == str(context.feed_id)
        # partition was created + marked materialized
        partition_entries = list(partitions.partitions.values())
        assert len(partition_entries) == 1
        assert partition_entries[0]["status"] == "MATERIALIZED"

    @pytest.mark.asyncio
    async def test_fetch_failure_marks_partition_failed_and_notifies_feed(self, context, wiring):
        _, bus, partitions, executor = wiring
        fetcher = _StubFetcher(pd.DataFrame(), raises=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            await executor.execute(
                feed=context,
                tick=NOW,
                fetcher=fetcher,
                feed_run_id=uuid.uuid4(),
            )
        assert fetcher.errors and isinstance(fetcher.errors[0], RuntimeError)
        assert all(p["status"] == "FAILED" for p in partitions.partitions.values())
        # Nothing should be published on the feed channel when fetch fails.
        assert bus.published == []
