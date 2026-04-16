"""FeedExecutor — runs a single feed tick end-to-end.

Supersedes the duplicated ``run_scheduled_feed`` / ``run_triggered_feed``
in ``ascent.engine.producer``. The executor is trigger-agnostic: the caller
(the async Runner) decides *when* to invoke it; the executor handles partition
creation, run tracking, publishing, and persistence enqueue.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import pandas as pd

from ascent.domain import PartitionWindow
from ascent.feeds.partition import partition_key_for, partition_window
from ascent.feeds.schedule import Schedule
from ascent.ports import EventBus, LatestFeedStore, PartitionRepository

logger = logging.getLogger(__name__)


class FeedFetcher(Protocol):
    """Thin abstraction over a user feed class. Keeps the executor free of
    SQLAlchemy-model dependencies.
    """

    async def fetch(self, partition: PartitionWindow, context: dict[str, Any]) -> pd.DataFrame: ...
    async def on_error(self, error: BaseException) -> None: ...


@dataclass(frozen=True)
class FeedContext:
    feed_id: uuid.UUID
    feed_ref: str
    channel: str
    output_table: str
    schedule: Schedule | None


@dataclass(frozen=True)
class FeedRunOutcome:
    feed_run_id: uuid.UUID
    partition_id: uuid.UUID | None
    partition_key: datetime | None
    rows: int
    produced_at: datetime


class FeedExecutor:
    def __init__(
        self,
        *,
        feed_store: LatestFeedStore,
        event_bus: EventBus,
        partition_repo: PartitionRepository,
    ) -> None:
        self._store = feed_store
        self._bus = event_bus
        self._partitions = partition_repo

    async def execute(
        self,
        *,
        feed: FeedContext,
        tick: datetime,
        fetcher: FeedFetcher,
        feed_run_id: uuid.UUID,
        extra_context: dict[str, Any] | None = None,
    ) -> FeedRunOutcome:
        partition_id, partition_info = await self._ensure_partition(feed, tick)

        try:
            df = await fetcher.fetch(partition_info, extra_context or {})
        except BaseException as exc:
            if partition_id is not None:
                await self._partitions.set_status(partition_id, "FAILED")
            await fetcher.on_error(exc)
            raise

        await self._store.put_latest(feed.feed_id, df, produced_at=tick)

        await self._bus.publish(
            feed.channel,
            {
                "feed_id": str(feed.feed_id),
                "feed_ref": feed.feed_ref,
                "timestamp": tick.isoformat(),
                "schema": feed.output_table,
                "feed_run_id": str(feed_run_id),
                "partition_key": (
                    partition_info.key.isoformat() if partition_info is not None else None
                ),
            },
        )

        if partition_id is not None:
            await self._partitions.set_status(partition_id, "MATERIALIZED")

        return FeedRunOutcome(
            feed_run_id=feed_run_id,
            partition_id=partition_id,
            partition_key=partition_info.key if partition_info else None,
            rows=len(df),
            produced_at=tick,
        )

    async def _ensure_partition(
        self, feed: FeedContext, tick: datetime
    ) -> tuple[uuid.UUID | None, PartitionWindow | None]:
        if feed.schedule is None:
            return None, None
        key = partition_key_for(feed.schedule, tick)
        w_start, w_end = partition_window(feed.schedule, key)
        partition_id = await self._partitions.find_or_create(
            feed_id=feed.feed_id,
            key=key,
            window_start=w_start,
            window_end=w_end,
        )
        return partition_id, PartitionWindow(key=key, window_start=w_start, window_end=w_end)
