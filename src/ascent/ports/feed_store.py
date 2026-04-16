"""FeedStore ports — split by access pattern.

``LatestFeedStore`` serves ``get_latest`` queries (Redis-backed in prod).
``HistoricalFeedStore`` serves ``get_range`` queries (TimescaleDB-backed).
``FeedStore`` is the composite: strategy-facing code only ever talks to this.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class LatestFeedStore(Protocol):
    """Hot cache of the most-recent feed observation."""

    async def put_latest(
        self, feed_id: uuid.UUID, df: pd.DataFrame, produced_at: datetime
    ) -> None: ...

    async def get_latest(self, feed_id: uuid.UUID) -> pd.DataFrame | None: ...

    async def get_latest_many(
        self, feed_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, pd.DataFrame | None]: ...

    async def is_warm(self, feed_id: uuid.UUID) -> bool: ...


@runtime_checkable
class HistoricalFeedStore(Protocol):
    """Durable range-query backing for feed data."""

    async def upsert(self, feed_id: uuid.UUID, output_table: str, df: pd.DataFrame) -> int: ...

    async def get_range(
        self,
        feed_id: uuid.UUID,
        output_table: str,
        *,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame: ...


@runtime_checkable
class FeedStore(LatestFeedStore, HistoricalFeedStore, Protocol):
    """Unified data-access surface. ``CompositeFeedStore`` is the production impl."""
