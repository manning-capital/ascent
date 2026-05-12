"""End-to-end provenance tests: strategy runs linking back to feed runs.

The ``StrategyRun → StrategyRunFeedRun → FeedRun`` chain is what powers the
UI's "which trades came from this feed run" and "what data caused this trade"
panels. Before the partitions→runs refactor, the join table existed but
nothing wrote to it — strategy evaluations never captured provenance.

Phase 2 of the refactor wired ``StrategyEvaluator`` to call
``strategy_run_repo.link_feed_runs`` after every evaluation. These tests
guard that wiring against regression.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import uuid
from datetime import UTC, datetime
from typing import ClassVar

import pandas as pd
import pytest
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ascent.application.context_builder import Context
from ascent.database.models import (
    Asset,
    AssetType,
    Attribute,
    Instrument,
    InstrumentType,
    Portfolio,
    Provider,
    ProviderType,
    StrategyRun,
    TradeStatusType,
)
from ascent.database.models.feeds import FeedInstrumentScope
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
from ascent.database.models.trades import Trade
from ascent.engine.deploy import deploy_feed, deploy_strategy
from ascent.engine.runner import Runner
from ascent.feeds.base import Feed
from ascent.feeds.output import InstrumentAttributes
from ascent.feeds.schedule import Schedule
from ascent.server.services import feed_service
from ascent.strategies.base import Strategy
from tests.factories import (
    make_asset,
    make_asset_type,
    make_attribute,
    make_instrument,
    make_instrument_type,
    make_portfolio,
    make_provider,
    make_provider_type,
    make_trade_status_type,
)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db_session: Session) -> dict:
    """Same baseline as test_feed_persistence but also seeds a portfolio + a
    PENDING TradeStatusType so Trade rows can be inserted for the reverse-
    lookup test.
    """
    asset_type = AssetType(**make_asset_type(name="CRYPTO"))
    provider_type = ProviderType(**make_provider_type(name="EXCHANGE"))
    instrument_type = InstrumentType(**make_instrument_type(name="SPOT_PAIR"))
    db_session.add_all([asset_type, provider_type, instrument_type])
    db_session.flush()

    btc = Asset(**make_asset(asset_type.id, name="BTC"))
    usd = Asset(**make_asset(asset_type.id, name="USD"))
    provider = Provider(**make_provider(provider_type.id, name="KRAKEN"))
    close_attr = Attribute(**make_attribute(name="CLOSE", display_name="Close"))
    portfolio = Portfolio(**make_portfolio(name="PROVENANCE_TEST"))
    pending_status = TradeStatusType(**make_trade_status_type("PENDING"))
    db_session.add_all([btc, usd, provider, close_attr, portfolio, pending_status])
    db_session.flush()

    btc_usd = Instrument(
        **make_instrument(instrument_type.id, provider.id, btc.id, usd.id, name="KRAKEN_BTC_USD")
    )
    db_session.add(btc_usd)
    db_session.commit()
    for obj in (btc_usd, provider, portfolio, close_attr, pending_status):
        db_session.refresh(obj)

    return {
        "btc_usd": btc_usd,
        "close_attr": close_attr,
        "provider": provider,
        "portfolio": portfolio,
        "pending_status": pending_status,
    }


# ---------------------------------------------------------------------------
# Strategy + feed fixtures — self-contained so we can assert provenance without
# touching trade routing or exchanges.
# ---------------------------------------------------------------------------


class _ProvFeed(Feed):
    class Parameters(BaseModel):
        value: float = 101.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_PAIR"
    display_name = "Provenance Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ids = self.get_universe()
        return pd.DataFrame(
            [{"instrument_id": str(iid), "CLOSE": self.parameters.value} for iid in ids]
        )


class _ProvStrategy(Strategy):
    class Parameters(BaseModel):
        pass

    feeds: ClassVar[list[type[Feed]]] = [_ProvFeed]
    portfolio = "PROVENANCE_TEST"
    display_name = "Provenance Strategy"

    def evaluate(self, ctx: Context) -> None:  # pragma: no cover - just needs to not raise
        # No-op: the whole point is that provenance is recorded even when the
        # strategy takes no action.
        _ = ctx


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


# ---------------------------------------------------------------------------
# Test 1 — evaluator populates strategy_run_feed_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_evaluation_records_feed_run_provenance(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    """Every strategy evaluation must write rows into ``strategy_run_feed_run``
    linking the strategy run to the feed runs it consulted. Without this
    linkage, the UI's Trade ↔ FeedRun provenance panels have nothing to show.
    """
    instrument_id = seeded["btc_usd"].id
    feed_id = deploy_feed(_ProvFeed, db_session)
    db_session.add(
        FeedInstrumentScope(
            feed_id=feed_id,
            instrument_id=instrument_id,
            order=1,
            added_at=datetime.now(UTC),
        )
    )
    strategy_id = deploy_strategy(_ProvStrategy, db_session)
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_ProvFeed)
    runner.add(_ProvStrategy)

    def has_link() -> bool:
        with Session(postgres_engine) as db:
            return (
                db.execute(
                    text("SELECT COUNT(*) FROM strategy_run_feed_run WHERE feed_id = :fid"),
                    {"fid": feed_id},
                ).scalar_one()
                >= 1
            )

    await _run_with_runner(runner, has_link, timeout=15.0)

    with Session(postgres_engine) as db:
        rows = db.execute(
            text(
                "SELECT srfr.strategy_run_id, srfr.feed_run_id, srfr.feed_id, srfr.is_trigger, "
                "       sr.strategy_id, fr.feed_id AS fr_feed_id "
                "FROM strategy_run_feed_run srfr "
                "JOIN strategy_run sr ON sr.id = srfr.strategy_run_id "
                "JOIN feed_run fr ON fr.id = srfr.feed_run_id "
                "WHERE srfr.feed_id = :fid "
                "ORDER BY sr.started_at LIMIT 1"
            ),
            {"fid": feed_id},
        ).one()

    _, feed_run_id, linked_feed_id, is_trigger, linked_strategy_id, fr_feed_id = rows
    assert linked_strategy_id == strategy_id
    assert linked_feed_id == feed_id
    assert fr_feed_id == feed_id
    # The only parent feed for this strategy fired, so it must be marked as
    # the trigger.
    assert is_trigger is True
    assert feed_run_id is not None


# ---------------------------------------------------------------------------
# Test 2 — /trades/{id}/feed-runs returns the runs the strategy consulted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trade_feed_runs_endpoint_surfaces_provenance(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    """After provenance links are written, a Trade attached to a strategy run
    must be able to look up the feed runs that were active when it was
    created — that's the whole point of the refactor's UI payoff.
    """
    instrument_id = seeded["btc_usd"].id
    portfolio = seeded["portfolio"]
    pending_status = seeded["pending_status"]

    feed_id = deploy_feed(_ProvFeed, db_session)
    db_session.add(
        FeedInstrumentScope(
            feed_id=feed_id,
            instrument_id=instrument_id,
            order=1,
            added_at=datetime.now(UTC),
        )
    )
    strategy_id = deploy_strategy(_ProvStrategy, db_session)
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_ProvFeed)
    runner.add(_ProvStrategy)

    def has_link() -> bool:
        with Session(postgres_engine) as db:
            return (
                db.execute(
                    text("SELECT COUNT(*) FROM strategy_run_feed_run WHERE feed_id = :fid"),
                    {"fid": feed_id},
                ).scalar_one()
                >= 1
            )

    await _run_with_runner(runner, has_link, timeout=15.0)

    # Manually create a trade bound to the strategy run so we can exercise the
    # reverse lookup. In production the router creates this row; here we skip
    # the exchange path since provenance is the concern.
    with Session(postgres_engine) as db:
        strategy_run_id = db.execute(
            text("SELECT strategy_run_id FROM strategy_run_feed_run WHERE feed_id = :fid LIMIT 1"),
            {"fid": feed_id},
        ).scalar_one()

        trade = Trade(
            strategy_id=strategy_id,
            strategy_run_id=strategy_run_id,
            current_status_type_id=pending_status.id,
            is_paper=True,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        trade_id = trade.id

    with Session(postgres_engine) as db:
        items = feed_service.get_trade_feed_runs(db, trade_id)

    assert items, "expected at least one feed_run linked to this trade"
    item = items[0]
    assert item.feed_id == feed_id
    assert item.feed_name == _ProvFeed.get_name()
    assert item.is_trigger is True
    assert item.snapshot_timestamp is not None
    # The run's snapshot must be recent — makes sure we didn't pick up a stale
    # row from an unrelated test.
    assert abs((datetime.now(tz=UTC) - item.snapshot_timestamp).total_seconds()) < 60


# ---------------------------------------------------------------------------
# Test 3 — /feeds/{id}/runs/{run_id}/trades returns trades caused by the run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feed_run_trades_endpoint_lists_caused_trades(
    postgres_engine, redis_url, nats_url, database_url, db_session, seeded
):
    """The forward direction: given a feed run, which trades did strategies
    create from evaluations that consulted it?
    """
    instrument_id = seeded["btc_usd"].id
    portfolio = seeded["portfolio"]
    pending_status = seeded["pending_status"]

    feed_id = deploy_feed(_ProvFeed, db_session)
    db_session.add(
        FeedInstrumentScope(
            feed_id=feed_id,
            instrument_id=instrument_id,
            order=1,
            added_at=datetime.now(UTC),
        )
    )
    strategy_id = deploy_strategy(_ProvStrategy, db_session)
    db_session.commit()

    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        nats_url=nats_url,
        include_writer=True,
        log_level="WARNING",
    )
    runner.add(_ProvFeed)
    runner.add(_ProvStrategy)

    def has_link() -> bool:
        with Session(postgres_engine) as db:
            return (
                db.execute(
                    text("SELECT COUNT(*) FROM strategy_run_feed_run WHERE feed_id = :fid"),
                    {"fid": feed_id},
                ).scalar_one()
                >= 1
            )

    await _run_with_runner(runner, has_link, timeout=15.0)

    with Session(postgres_engine) as db:
        row = db.execute(
            text(
                "SELECT strategy_run_id, feed_run_id FROM strategy_run_feed_run "
                "WHERE feed_id = :fid LIMIT 1"
            ),
            {"fid": feed_id},
        ).one()
        strategy_run_id, feed_run_id = row

        trade = Trade(
            strategy_id=strategy_id,
            strategy_run_id=strategy_run_id,
            current_status_type_id=pending_status.id,
            is_paper=True,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        expected_trade_id = trade.id

    with Session(postgres_engine) as db:
        items = feed_service.get_run_trades(db, feed_id, feed_run_id)

    assert len(items) == 1
    item = items[0]
    assert item.trade_id == expected_trade_id
    assert item.strategy_id == strategy_id
    assert item.strategy_run_id == strategy_run_id
    assert item.status == "PENDING"
    # Silence unused-import warnings when this file is imported in isolation.
    _ = (StrategyRun, StrategyRunFeedRun, _dt)
