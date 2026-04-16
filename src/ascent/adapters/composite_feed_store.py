"""CompositeFeedStore — the unified data-access surface.

Strategy authors and engine code only ever see :class:`FeedStore`. This
composite routes ``put_latest`` / ``get_latest*`` to the hot Redis cache and
``get_range`` / ``upsert`` to the durable Timescale store — transparent to
the caller.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from ascent.ports import FeedStore, HistoricalFeedStore, LatestFeedStore


class CompositeFeedStore(FeedStore):
    def __init__(
        self,
        *,
        latest: LatestFeedStore,
        historical: HistoricalFeedStore,
    ) -> None:
        self._latest = latest
        self._historical = historical

    # -------- LatestFeedStore --------

    async def put_latest(self, feed_id: uuid.UUID, df: pd.DataFrame, produced_at: datetime) -> None:
        await self._latest.put_latest(feed_id, df, produced_at)

    async def get_latest(self, feed_id: uuid.UUID) -> pd.DataFrame | None:
        return await self._latest.get_latest(feed_id)

    async def get_latest_many(
        self, feed_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, pd.DataFrame | None]:
        return await self._latest.get_latest_many(feed_ids)

    async def is_warm(self, feed_id: uuid.UUID) -> bool:
        return await self._latest.is_warm(feed_id)

    # -------- HistoricalFeedStore --------

    async def upsert(self, feed_id: uuid.UUID, output_table: str, df: pd.DataFrame) -> int:
        return await self._historical.upsert(feed_id, output_table, df)

    async def get_range(
        self,
        feed_id: uuid.UUID,
        output_table: str,
        *,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        return await self._historical.get_range(feed_id, output_table, start=start, end=end)
