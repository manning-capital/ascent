"""End-to-end persistence tests driven through the real :class:`Runner`.

Each test boots a live ``Runner`` against TimescaleDB + Redis + NATS, runs one
or more feeds for a few ticks, then asserts the expected rows land in the EAV
hypertables (``instrument_attribute`` or ``composite_attribute``).

Covered scenarios:

* multi-tick: several consecutive ticks each persist with a distinct partition
  timestamp (catches "only the first tick writes" and "upsert overwrites
  history" bugs).
* multi-entity + multi-attribute: universe of several instruments emitting
  several attributes, every ``(entity, attribute)`` combination lands.
* composite-scoped feed: rows route to ``composite_attribute``.
* triggered chain (``depends_on``): parent scheduled feed fires child
  triggered feed; both outputs persist.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import ClassVar

import pandas as pd
import pytest
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ascent.database.models import (
    Asset,
    AssetType,
    Attribute,
    Composite,
    CompositeMember,
    CompositeType,
    Instrument,
    InstrumentType,
    Provider,
    ProviderType,
)
from ascent.database.models.feeds import FeedCompositeScope, FeedInstrumentScope, FeedPartition
from ascent.engine.deploy import deploy_feed
from ascent.engine.runner import Runner
from ascent.feeds.base import Feed
from ascent.feeds.output import CompositeAttributes, InstrumentAttributes
from ascent.feeds.schedule import Schedule
from ascent.server.services import feed_service
from tests.factories import (
    make_asset,
    make_asset_type,
    make_attribute,
    make_composite,
    make_composite_member,
    make_composite_type,
    make_instrument,
    make_instrument_type,
    make_provider,
    make_provider_type,
)


# ---------------------------------------------------------------------------
# Shared seeding
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db_session: Session) -> dict:
    """Baseline seed: KRAKEN provider, SPOT_PAIR instrument type, two instruments
    (BTC/USD, ETH/USD), and CLOSE + VOLUME attribute rows.
    """
    asset_type = AssetType(**make_asset_type(name="CRYPTO"))
    provider_type = ProviderType(**make_provider_type(name="EXCHANGE"))
    instrument_type = InstrumentType(**make_instrument_type(name="SPOT_PAIR"))
    db_session.add_all([asset_type, provider_type, instrument_type])
    db_session.flush()

    btc = Asset(**make_asset(asset_type.id, name="BTC"))
    eth = Asset(**make_asset(asset_type.id, name="ETH"))
    usd = Asset(**make_asset(asset_type.id, name="USD"))
    provider = Provider(**make_provider(provider_type.id, name="KRAKEN"))
    close_attr = Attribute(**make_attribute(name="CLOSE", display_name="Close"))
    volume_attr = Attribute(**make_attribute(name="VOLUME", display_name="Volume"))
    db_session.add_all([btc, eth, usd, provider, close_attr, volume_attr])
    db_session.flush()

    btc_usd = Instrument(
        **make_instrument(
            instrument_type.id, provider.id, btc.id, usd.id, name="KRAKEN_BTC_USD"
        )
    )
    eth_usd = Instrument(
        **make_instrument(
            instrument_type.id, provider.id, eth.id, usd.id, name="KRAKEN_ETH_USD"
        )
    )
    db_session.add_all([btc_usd, eth_usd])
    db_session.commit()
    for obj in (btc_usd, eth_usd, close_attr, volume_attr, provider, instrument_type):
        db_session.refresh(obj)

    return {
        "btc_usd": btc_usd,
        "eth_usd": eth_usd,
        "close_attr": close_attr,
        "volume_attr": volume_attr,
        "provider": provider,
        "instrument_type": instrument_type,
        "asset_type": asset_type,
    }


@pytest.fixture
def seeded_with_composite(db_session: Session, seeded: dict) -> dict:
    """Extends ``seeded`` with a ``SPREAD`` composite type plus one BTC/ETH composite."""
    composite_type = CompositeType(**make_composite_type(name="SPREAD"))
    db_session.add(composite_type)
    db_session.flush()

    composite = Composite(**make_composite(composite_type.id, name="BTC_ETH_SPREAD"))
    db_session.add(composite)
    db_session.flush()

    db_session.add_all(
        [
            CompositeMember(
                **make_composite_member(composite.id, seeded["btc_usd"].id, order=1)
            ),
            CompositeMember(
                **make_composite_member(composite.id, seeded["eth_usd"].id, order=2)
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(composite)
    db_session.refresh(composite_type)

    return {**seeded, "composite": composite, "composite_type": composite_type}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_until(predicate, *, timeout: float) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return predicate()


async def _run_with_runner(runner: Runner, predicate, *, timeout: float) -> None:
    """Run ``runner._run_async()`` as a task, wait for predicate, then cancel."""
    task = asyncio.create_task(runner._run_async())
    try:
        ok = await _wait_until(predicate, timeout=timeout)
        if not ok:
            pytest.fail(f"predicate never became true within {timeout}s")
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


def _count_distinct_timestamps(engine, table: str, entity_col: str, entity_id: uuid.UUID) -> int:
    with Session(engine) as db:
        return db.execute(
            text(
                f"SELECT COUNT(DISTINCT timestamp) FROM {table} "
                f"WHERE {entity_col} = :eid"
            ),
            {"eid": entity_id},
        ).scalar_one()


def _row_count(engine, table: str, entity_col: str, entity_id: uuid.UUID) -> int:
    with Session(engine) as db:
        return db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {entity_col} = :eid"),
            {"eid": entity_id},
        ).scalar_one()


# ---------------------------------------------------------------------------
# Test 1 — multi-tick persistence produces distinct partition timestamps
# ---------------------------------------------------------------------------


class _MultiTickFeed(Feed):
    class Parameters(BaseModel):
        value: float = 42.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Multi Tick Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"instrument_id": str(iid), "CLOSE": self.parameters.value} for iid in ids]
        )


@pytest.mark.asyncio
async def test_multiple_ticks_produce_distinct_partition_timestamps(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    instrument_id = seeded["btc_usd"].id
    feed_id = deploy_feed(_MultiTickFeed, db_session)
    db_session.add(FeedInstrumentScope(feed_id=feed_id, instrument_id=instrument_id, order=1))
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_MultiTickFeed)

    await _run_with_runner(
        runner,
        lambda: _count_distinct_timestamps(
            postgres_engine, "instrument_attribute", "instrument_id", instrument_id
        )
        >= 3,
        timeout=10.0,
    )

    with Session(postgres_engine) as db:
        timestamps = db.execute(
            text(
                "SELECT DISTINCT timestamp FROM instrument_attribute "
                "WHERE instrument_id = :iid ORDER BY timestamp"
            ),
            {"iid": instrument_id},
        ).scalars().all()
    # 3 ticks at 1s interval must have 3 distinct partition times; boundaries
    # must be in increasing order (the engine stamps the partition key, not wall
    # clock) — dedupe sanity-checks the ON CONFLICT path didn't collapse them.
    assert len(timestamps) >= 3
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# Test 2 — multi-instrument + multi-attribute per tick
# ---------------------------------------------------------------------------


class _MultiAttrFeed(Feed):
    class Parameters(BaseModel):
        close_value: float = 100.0
        volume_value: float = 500.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Multi Attr Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [
                {
                    "instrument_id": str(iid),
                    "CLOSE": self.parameters.close_value,
                    "VOLUME": self.parameters.volume_value,
                }
                for iid in ids
            ]
        )


@pytest.mark.asyncio
async def test_multi_entity_multi_attribute_persists_every_combination(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    btc_id = seeded["btc_usd"].id
    eth_id = seeded["eth_usd"].id
    close_id = seeded["close_attr"].id
    volume_id = seeded["volume_attr"].id

    feed_id = deploy_feed(_MultiAttrFeed, db_session)
    db_session.add_all(
        [
            FeedInstrumentScope(feed_id=feed_id, instrument_id=btc_id, order=1),
            FeedInstrumentScope(feed_id=feed_id, instrument_id=eth_id, order=2),
        ]
    )
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_MultiAttrFeed)

    def all_combos_present() -> bool:
        with Session(postgres_engine) as db:
            pairs = set(
                db.execute(
                    text(
                        "SELECT DISTINCT instrument_id, attribute_id "
                        "FROM instrument_attribute WHERE instrument_id IN (:btc, :eth)"
                    ),
                    {"btc": btc_id, "eth": eth_id},
                ).all()
            )
        expected = {(btc_id, close_id), (btc_id, volume_id), (eth_id, close_id), (eth_id, volume_id)}
        return expected.issubset(pairs)

    await _run_with_runner(runner, all_combos_present, timeout=10.0)

    with Session(postgres_engine) as db:
        rows = db.execute(
            text(
                "SELECT instrument_id, attribute_id, attribute_value "
                "FROM instrument_attribute WHERE instrument_id IN (:btc, :eth) "
                "ORDER BY timestamp DESC LIMIT 4"
            ),
            {"btc": btc_id, "eth": eth_id},
        ).all()
    values_by_pair = {(iid, aid): val for iid, aid, val in rows}
    # Every combination of the 2 instruments × 2 attributes must be present
    # and carry the configured parameter value.
    assert values_by_pair[(btc_id, close_id)] == 100.0
    assert values_by_pair[(btc_id, volume_id)] == 500.0
    assert values_by_pair[(eth_id, close_id)] == 100.0
    assert values_by_pair[(eth_id, volume_id)] == 500.0


# ---------------------------------------------------------------------------
# Test 3 — composite-scoped feed routes to composite_attribute
# ---------------------------------------------------------------------------


class _CompositeFeed(Feed):
    class Parameters(BaseModel):
        value: float = 7.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    display_name = "Composite Feed"

    def fetch(self) -> DataFrame[CompositeAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"composite_id": str(cid), "CLOSE": self.parameters.value} for cid in ids]
        )


@pytest.mark.asyncio
async def test_composite_scoped_feed_writes_to_composite_attribute(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded_with_composite
):
    composite_id = seeded_with_composite["composite"].id
    close_id = seeded_with_composite["close_attr"].id

    feed_id = deploy_feed(_CompositeFeed, db_session)
    db_session.add(FeedCompositeScope(feed_id=feed_id, composite_id=composite_id, order=1))
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_CompositeFeed)

    await _run_with_runner(
        runner,
        lambda: _row_count(
            postgres_engine, "composite_attribute", "composite_id", composite_id
        )
        >= 1,
        timeout=10.0,
    )

    with Session(postgres_engine) as db:
        rows = db.execute(
            text(
                "SELECT attribute_id, attribute_value FROM composite_attribute "
                "WHERE composite_id = :cid"
            ),
            {"cid": composite_id},
        ).all()
        # Composite-scoped feeds must not leak into instrument_attribute.
        inst_rows = db.execute(
            text("SELECT COUNT(*) FROM instrument_attribute")
        ).scalar_one()

    assert rows, "expected at least one composite_attribute row"
    for attr_id, val in rows:
        assert attr_id == close_id
        assert val == 7.0
    assert inst_rows == 0


# ---------------------------------------------------------------------------
# Test 4 — triggered feed chain (parent scheduled → child depends_on)
# ---------------------------------------------------------------------------


class _ParentFeed(Feed):
    class Parameters(BaseModel):
        value: float = 10.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Parent Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"instrument_id": str(iid), "CLOSE": self.parameters.value} for iid in ids]
        )


class _ChildFeed(Feed):
    depends_on: ClassVar[list[type[Feed]]] = [_ParentFeed]
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Child Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        parent = self.get_feed(_ParentFeed)
        if parent.empty:
            return pd.DataFrame(columns=["instrument_id", "VOLUME"])
        # Emit a derived attribute (VOLUME = CLOSE * 2) against the parent's
        # row set — proves triggered fetch actually consumes the parent frame.
        return pd.DataFrame(
            [
                {"instrument_id": row["instrument_id"], "VOLUME": float(row["CLOSE"]) * 2}
                for _, row in parent.iterrows()
            ]
        )


@pytest.mark.asyncio
async def test_triggered_feed_chain_persists_both_parent_and_child(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    instrument_id = seeded["btc_usd"].id
    close_id = seeded["close_attr"].id
    volume_id = seeded["volume_attr"].id

    # Deploy parent first — the child's FeedDependency row needs the parent id.
    parent_id = deploy_feed(_ParentFeed, db_session)
    db_session.add(
        FeedInstrumentScope(feed_id=parent_id, instrument_id=instrument_id, order=1)
    )
    db_session.commit()

    child_id = deploy_feed(_ChildFeed, db_session)
    db_session.add(
        FeedInstrumentScope(feed_id=child_id, instrument_id=instrument_id, order=1)
    )
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_ParentFeed)
    runner.add(_ChildFeed)

    def both_attrs_present() -> bool:
        with Session(postgres_engine) as db:
            attrs = set(
                db.execute(
                    text(
                        "SELECT DISTINCT attribute_id FROM instrument_attribute "
                        "WHERE instrument_id = :iid"
                    ),
                    {"iid": instrument_id},
                )
                .scalars()
                .all()
            )
        return {close_id, volume_id}.issubset(attrs)

    await _run_with_runner(runner, both_attrs_present, timeout=15.0)

    with Session(postgres_engine) as db:
        parent_val = db.execute(
            text(
                "SELECT attribute_value FROM instrument_attribute "
                "WHERE instrument_id = :iid AND attribute_id = :aid "
                "ORDER BY timestamp DESC LIMIT 1"
            ),
            {"iid": instrument_id, "aid": close_id},
        ).scalar_one()
        child_val = db.execute(
            text(
                "SELECT attribute_value FROM instrument_attribute "
                "WHERE instrument_id = :iid AND attribute_id = :aid "
                "ORDER BY timestamp DESC LIMIT 1"
            ),
            {"iid": instrument_id, "aid": volume_id},
        ).scalar_one()
    assert parent_val == 10.0
    # Child reads parent frame at fetch time and derives VOLUME = CLOSE * 2.
    assert child_val == 20.0


# ---------------------------------------------------------------------------
# Test 5 — /feeds/{id}/partitions/{id}/data returns the persisted row
# ---------------------------------------------------------------------------


class _PartitionVisibleFeed(Feed):
    class Parameters(BaseModel):
        value: float = 55.5

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Partition Visible Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"instrument_id": str(iid), "CLOSE": self.parameters.value} for iid in ids]
        )


@pytest.mark.asyncio
async def test_ui_partition_data_endpoint_sees_persisted_rows(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    """Guards the partition-window / persist-timestamp alignment the UI depends on.

    The UI's ``GET /feeds/{id}/partitions/{id}/data`` page filters the EAV
    hypertable by ``timestamp >= partition.window_start AND timestamp <
    partition.window_end``. Since the persister stamps
    ``timestamp = partition.key`` (``= window_start``), a naive ``>`` instead
    of ``>=`` — or any timezone / precision drift — would make the UI show an
    empty Partition tab even though rows *are* in the DB. That's the exact
    failure mode reported in production.
    """
    instrument_id = seeded["btc_usd"].id
    close_id = seeded["close_attr"].id

    feed_id = deploy_feed(_PartitionVisibleFeed, db_session)
    db_session.add(FeedInstrumentScope(feed_id=feed_id, instrument_id=instrument_id, order=1))
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_PartitionVisibleFeed)

    await _run_with_runner(
        runner,
        lambda: _row_count(
            postgres_engine, "instrument_attribute", "instrument_id", instrument_id
        )
        >= 1,
        timeout=10.0,
    )

    # Pick any MATERIALIZED partition for this feed and ask the UI endpoint
    # what it has — exactly the query the "Partition" tab runs.
    with Session(postgres_engine) as db:
        partition = db.execute(
            text(
                "SELECT id FROM feed_partition "
                "WHERE feed_id = :fid AND status = 'MATERIALIZED' "
                "ORDER BY partition_key LIMIT 1"
            ),
            {"fid": feed_id},
        ).scalar_one_or_none()
    assert partition is not None, "feed ran but no partition was marked MATERIALIZED"

    with Session(postgres_engine) as db:
        response = feed_service.get_partition_data(
            db, feed_id, partition, page=1, page_size=50
        )

    assert response.total >= 1, (
        f"UI partition-data query returned 0 rows for partition {partition} "
        f"even though the table has rows — persist timestamp does not align "
        f"with partition.window_start/window_end"
    )
    # Pivoted shape: one row per instrument, with the attribute display_name
    # (resolved from attribute.display_name via JOIN) as a column.
    item = response.items[0]
    assert str(item["instrument_id"]) == str(instrument_id)
    assert item[seeded["close_attr"].display_name] == 55.5
    _ = close_id  # referenced so the attribute seed isn't garbage-collected


# ---------------------------------------------------------------------------
# Test 6 — feed_run.partition_id is backfilled after partition creation
# ---------------------------------------------------------------------------


class _RunLinkFeed(Feed):
    class Parameters(BaseModel):
        value: float = 1.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Run Link Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"instrument_id": str(iid), "CLOSE": self.parameters.value} for iid in ids]
        )


@pytest.mark.asyncio
async def test_feed_run_is_linked_to_its_partition(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    """Regression: the UI's ``/feeds/{id}/runs/{run_id}?tab=Partition`` view
    loads partition data by ``feed_run.partition_id``. If the services create
    the ``FeedRun`` row before the executor creates the partition (and never
    backfill), every run row ships with ``partition_id = NULL`` and the tab
    renders empty even though the hypertable has rows.
    """
    instrument_id = seeded["btc_usd"].id
    feed_id = deploy_feed(_RunLinkFeed, db_session)
    db_session.add(FeedInstrumentScope(feed_id=feed_id, instrument_id=instrument_id, order=1))
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_RunLinkFeed)

    def has_completed_run_with_partition() -> bool:
        with Session(postgres_engine) as db:
            return (
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM feed_run "
                        "WHERE feed_id = :fid AND status = 'COMPLETED' "
                        "AND partition_id IS NOT NULL"
                    ),
                    {"fid": feed_id},
                ).scalar_one()
                >= 1
            )

    await _run_with_runner(runner, has_completed_run_with_partition, timeout=10.0)

    with Session(postgres_engine) as db:
        runs = db.execute(
            text(
                "SELECT id, partition_id FROM feed_run "
                "WHERE feed_id = :fid AND status = 'COMPLETED' "
                "ORDER BY started_at"
            ),
            {"fid": feed_id},
        ).all()
    # Every successfully completed run must point to the partition that
    # received its output — the UI's run-detail → partition-tab flow depends
    # on this join.
    assert runs, "no completed runs produced"
    for run_id, partition_id in runs:
        assert partition_id is not None, f"run {run_id} has NULL partition_id"
        with Session(postgres_engine) as db:
            partition_matches = db.execute(
                text("SELECT feed_id FROM feed_partition WHERE id = :pid"),
                {"pid": partition_id},
            ).scalar_one()
        assert partition_matches == feed_id
