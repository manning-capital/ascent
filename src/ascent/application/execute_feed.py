"""FeedExecutor — runs a single feed tick end-to-end.

The executor is trigger-agnostic: the caller (the async Runner) decides *when*
to invoke it. The executor computes the canonical ``snapshot_timestamp`` from
the feed's schedule, runs the user fetcher, writes latest to Redis, and
publishes the feed event.

``snapshot_timestamp`` replaces the prior ``FeedPartition`` concept. There's
no partition table, no grid, no MATERIALIZED/FAILED partition state — just a
timestamp that downstream code (strategies, persister, UI) uses to align data.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import pandas as pd

from ascent.feeds.schedule import Schedule
from ascent.feeds.snapshot import snapshot_timestamp_for
from ascent.ports import EventBus, LatestFeedStore

logger = logging.getLogger(__name__)


class FeedFetcher(Protocol):
    """Thin abstraction over a user feed class."""

    async def fetch(self, snapshot_timestamp: datetime, context: dict[str, Any]) -> pd.DataFrame: ...
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
    snapshot_timestamp: datetime
    rows: int
    produced_at: datetime


class FeedExecutor:
    def __init__(
        self,
        *,
        feed_store: LatestFeedStore,
        event_bus: EventBus,
    ) -> None:
        self._store = feed_store
        self._bus = event_bus

    @staticmethod
    def resolve_snapshot(feed: FeedContext, tick: datetime) -> datetime:
        """Schedule-aligned snapshot timestamp for ``tick``, or ``tick`` itself
        if the feed has no schedule (triggered feeds inherit the parent's
        snapshot, which is passed in as ``tick``).
        """
        if feed.schedule is None:
            return tick
        return snapshot_timestamp_for(feed.schedule, tick)

    async def execute(
        self,
        *,
        feed: FeedContext,
        tick: datetime,
        snapshot_timestamp: datetime,
        fetcher: FeedFetcher,
        feed_run_id: uuid.UUID,
        extra_context: dict[str, Any] | None = None,
    ) -> FeedRunOutcome:
        try:
            df = await fetcher.fetch(snapshot_timestamp, extra_context or {})
        except BaseException as exc:
            await fetcher.on_error(exc)
            raise

        await self._store.put_latest(feed.feed_id, df, produced_at=tick)

        await self._bus.publish(
            feed.channel,
            {
                "feed_id": str(feed.feed_id),
                "feed_ref": feed.feed_ref,
                "snapshot_timestamp": snapshot_timestamp.isoformat(),
                "schema": feed.output_table,
                "feed_run_id": str(feed_run_id),
            },
        )

        return FeedRunOutcome(
            feed_run_id=feed_run_id,
            snapshot_timestamp=snapshot_timestamp,
            rows=len(df),
            produced_at=tick,
        )
