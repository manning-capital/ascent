"""FeedPersister — unpivots the wide feed frame and upserts to the EAV store.

Feeds emit wide frames with one row per entity (instrument or composite) and
one column per attribute (column name == ``Attribute.name``). The persister
is the single place that knows about the EAV schema: it melts the frame to
``(timestamp, entity_id, attribute_id, attribute_value)`` rows, stamps the
partition timestamp, resolves attribute names to UUIDs, and upserts.

Called off the hot path (subscribed to feed channels on the event bus), so
the strategy consumer doesn't wait for the DB write. The upsert is keyed by
the composite PK so replays are idempotent.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Protocol

import pandas as pd

from ascent.ports import HistoricalFeedStore, LatestFeedStore

logger = logging.getLogger(__name__)


class AttributeResolver(Protocol):
    """Resolves attribute name -> attribute UUID, or ``None`` if unknown."""

    def attribute_id_for_name(self, name: str) -> uuid.UUID | None: ...


_RESERVED_COLS = frozenset({"instrument_id", "composite_id", "period_id"})


class FeedPersister:
    def __init__(
        self,
        *,
        latest_store: LatestFeedStore,
        historical_store: HistoricalFeedStore,
        attribute_resolver: AttributeResolver,
    ) -> None:
        self._latest = latest_store
        self._historical = historical_store
        self._attrs = attribute_resolver

    async def persist(
        self,
        *,
        feed_id: uuid.UUID,
        output_table: str,
        timestamp: datetime,
    ) -> int:
        df = await self._latest.get_latest(feed_id)
        if df is None or df.empty:
            logger.debug("FeedPersister: no data for feed %s", feed_id)
            return 0

        try:
            long_df = self._unpivot(df, timestamp)
        except ValueError:
            logger.exception("FeedPersister: cannot unpivot feed %s frame", feed_id)
            return 0

        if long_df.empty:
            return 0

        rows = await self._historical.upsert(feed_id, output_table, long_df)
        logger.debug(
            "FeedPersister: upserted %d rows for feed %s to %s", rows, feed_id, output_table
        )
        return rows

    def _unpivot(self, df: pd.DataFrame, timestamp: datetime) -> pd.DataFrame:
        entity_col = self._entity_col(df)
        id_vars = [c for c in df.columns if c in _RESERVED_COLS]
        value_vars = [c for c in df.columns if c not in _RESERVED_COLS]
        if not value_vars:
            return pd.DataFrame()

        unknown = [name for name in value_vars if self._attrs.attribute_id_for_name(name) is None]
        if unknown:
            raise ValueError(
                f"FeedPersister: unknown attribute names {unknown!r} — "
                "no matching Attribute row in the DB"
            )

        long_df = df.melt(
            id_vars=id_vars,
            value_vars=value_vars,
            var_name="attribute_name",
            value_name="attribute_value",
        )
        long_df = long_df.dropna(subset=["attribute_value"])
        long_df["attribute_id"] = long_df["attribute_name"].map(
            lambda n: self._attrs.attribute_id_for_name(n)
        )
        long_df["timestamp"] = pd.Timestamp(timestamp)
        long_df = long_df.drop(columns=["attribute_name"])

        # Reorder columns so the PK sits at the front (cosmetic only).
        leading = ["timestamp", entity_col]
        if "period_id" in id_vars:
            leading.append("period_id")
        leading.append("attribute_id")
        ordered = leading + [c for c in long_df.columns if c not in leading]
        return long_df[ordered]

    @staticmethod
    def _entity_col(df: pd.DataFrame) -> str:
        if "composite_id" in df.columns:
            return "composite_id"
        if "instrument_id" in df.columns:
            return "instrument_id"
        raise ValueError(
            "FeedPersister: wide frame missing 'instrument_id' or 'composite_id' column"
        )
