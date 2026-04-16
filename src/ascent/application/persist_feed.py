"""FeedPersister — upserts a feed DataFrame to the historical store.

Called off the hot path (subscribed to feed channels on the event bus), so
the strategy consumer doesn't wait for the DB write. The upsert is keyed by
timestamp + partition key so replays are idempotent.
"""

from __future__ import annotations

import logging
import uuid

from ascent.ports import HistoricalFeedStore, LatestFeedStore

logger = logging.getLogger(__name__)


class FeedPersister:
    def __init__(
        self,
        *,
        latest_store: LatestFeedStore,
        historical_store: HistoricalFeedStore,
    ) -> None:
        self._latest = latest_store
        self._historical = historical_store

    async def persist(self, *, feed_id: uuid.UUID, output_table: str) -> int:
        df = await self._latest.get_latest(feed_id)
        if df is None or df.empty:
            logger.debug("FeedPersister: no data for feed %s", feed_id)
            return 0
        rows = await self._historical.upsert(feed_id, output_table, df)
        logger.debug(
            "FeedPersister: upserted %d rows for feed %s to %s", rows, feed_id, output_table
        )
        return rows
