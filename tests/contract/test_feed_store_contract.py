"""Contract tests for :class:`ascent.ports.FeedStore`.

The hottest bug surface here is the DataFrame round-trip: Redis stores JSON,
so any backend going through JSON must preserve the wide-format columns that
the strategy context builder depends on (``instrument_id``/``composite_id``
plus one column per attribute name).

The historical side still upserts the melted EAV rows produced by
:class:`ascent.application.persist_feed.FeedPersister` — timestamp + entity id
+ attribute id + attribute value.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pandas as pd
import pytest

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 16, 12, 0, 15, tzinfo=UTC)


def _wide_df() -> pd.DataFrame:
    """The exact shape feeds publish — matches the example feeds."""
    return pd.DataFrame(
        [
            {"instrument_id": str(uuid.uuid4()), "CLOSE": 123.45, "VOLUME": 1000.0},
            {"instrument_id": str(uuid.uuid4()), "CLOSE": 67.89, "VOLUME": 2000.0},
        ]
    )


def _long_df() -> pd.DataFrame:
    """The melted EAV shape the persister hands to the historical store."""
    return pd.DataFrame(
        [
            {
                "timestamp": NOW,
                "instrument_id": str(uuid.uuid4()),
                "attribute_id": str(uuid.uuid4()),
                "attribute_value": 123.45,
            },
            {
                "timestamp": NOW,
                "instrument_id": str(uuid.uuid4()),
                "attribute_id": str(uuid.uuid4()),
                "attribute_value": 67.89,
            },
        ]
    )


class TestLatestRoundTrip:
    @pytest.mark.asyncio
    async def test_put_and_get_latest(self, feed_store):
        feed_id = uuid.uuid4()
        df = _wide_df()
        await feed_store.put_latest(feed_id, df, produced_at=NOW)

        fetched = await feed_store.get_latest(feed_id)
        assert fetched is not None
        assert len(fetched) == 2
        assert set(fetched.columns) >= {"instrument_id", "CLOSE", "VOLUME"}
        assert fetched["CLOSE"].tolist() == [123.45, 67.89]

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, feed_store):
        assert await feed_store.get_latest(uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_put_overwrites_previous(self, feed_store):
        feed_id = uuid.uuid4()
        await feed_store.put_latest(feed_id, _wide_df(), produced_at=NOW)
        new_df = pd.DataFrame([{"instrument_id": str(uuid.uuid4()), "CLOSE": 999.0}])
        await feed_store.put_latest(feed_id, new_df, produced_at=LATER)

        fetched = await feed_store.get_latest(feed_id)
        assert len(fetched) == 1
        assert fetched["CLOSE"].iloc[0] == 999.0

    @pytest.mark.asyncio
    async def test_is_warm_reflects_put(self, feed_store):
        feed_id = uuid.uuid4()
        assert not await feed_store.is_warm(feed_id)
        await feed_store.put_latest(feed_id, _wide_df(), produced_at=NOW)
        assert await feed_store.is_warm(feed_id)


class TestBatchFetch:
    @pytest.mark.asyncio
    async def test_get_latest_many_returns_mapping_with_none_for_missing(self, feed_store):
        have = uuid.uuid4()
        missing = uuid.uuid4()
        await feed_store.put_latest(have, _wide_df(), produced_at=NOW)

        out = await feed_store.get_latest_many([have, missing])
        assert out[missing] is None
        assert out[have] is not None and len(out[have]) == 2

    @pytest.mark.asyncio
    async def test_get_latest_many_empty_input_returns_empty(self, feed_store):
        assert await feed_store.get_latest_many([]) == {}


class TestHistoricalUpsert:
    """These assertions only make sense for backends that implement the
    historical side of the port. We skip when the fake doesn't.
    """

    @pytest.mark.asyncio
    async def test_upsert_returns_rowcount(self, feed_store):
        if not hasattr(feed_store, "upsert"):
            pytest.skip("backend does not implement HistoricalFeedStore")
        n = await feed_store.upsert(uuid.uuid4(), "instrument_attribute", _long_df())
        assert n == 2

    @pytest.mark.asyncio
    async def test_upsert_empty_dataframe_is_noop(self, feed_store):
        if not hasattr(feed_store, "upsert"):
            pytest.skip("backend does not implement HistoricalFeedStore")
        n = await feed_store.upsert(uuid.uuid4(), "instrument_attribute", pd.DataFrame())
        assert n == 0
