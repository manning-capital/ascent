"""In-memory FeedStore — serves as both LatestFeedStore and HistoricalFeedStore."""

from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from ascent.ports import FeedStore


class InMemoryFeedStore(FeedStore):
    def __init__(self) -> None:
        self._latest: dict[uuid.UUID, tuple[pd.DataFrame, datetime]] = {}
        self._history: dict[uuid.UUID, list[pd.DataFrame]] = {}
        self.upserts: list[tuple[uuid.UUID, str, int]] = []

    # ------- LatestFeedStore -------

    async def put_latest(self, feed_id: uuid.UUID, df: pd.DataFrame, produced_at: datetime) -> None:
        self._latest[feed_id] = (df.copy(), produced_at)

    async def get_latest(self, feed_id: uuid.UUID) -> pd.DataFrame | None:
        entry = self._latest.get(feed_id)
        return None if entry is None else entry[0].copy()

    async def get_latest_many(
        self, feed_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, pd.DataFrame | None]:
        return {fid: await self.get_latest(fid) for fid in feed_ids}

    async def is_warm(self, feed_id: uuid.UUID) -> bool:
        return feed_id in self._latest

    # ------- HistoricalFeedStore -------

    async def upsert(self, feed_id: uuid.UUID, output_table: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self._history.setdefault(feed_id, []).append(df.copy())
        self.upserts.append((feed_id, output_table, len(df)))
        return len(df)

    async def get_range(
        self,
        feed_id: uuid.UUID,
        output_table: str,
        *,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        frames = self._history.get(feed_id, [])
        if not frames:
            return pd.DataFrame()
        merged = pd.concat(frames, ignore_index=True)
        if "timestamp" in merged.columns:
            ts = pd.to_datetime(merged["timestamp"], utc=True)
            mask = (ts >= start) & (ts < end)
            merged = merged.loc[mask]
        return merged.reset_index(drop=True)
