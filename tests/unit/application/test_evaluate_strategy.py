"""StrategyEvaluator tests — cover the wide-format feed frame flow and the
``strategy_run → feed_run`` provenance linkage that ships with the partitions-
to-runs refactor.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pandas as pd
import pytest

from ascent.application.context_builder import Context
from ascent.application.evaluate_strategy import FeedBinding, StrategyEvaluator
from ascent.application.trigger import StrategyFeedSpec
from ascent.ports import Event
from tests.fakes import (
    FakeClock,
    FakeRunTracker,
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryFeedStore,
    InMemoryStrategyRunRepository,
    InMemoryStrategyUniverseRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _wide_rows(instrument_id: uuid.UUID, price: float) -> pd.DataFrame:
    return pd.DataFrame([{"instrument_id": str(instrument_id), "CLOSE": price}])


def _make_service(
    *,
    strategy_id: uuid.UUID,
    feed_bindings: list[FeedBinding],
    universe_repo: InMemoryStrategyUniverseRepository,
    store: InMemoryFeedStore,
    evaluator,
    strategy_run_repo: InMemoryStrategyRunRepository | None = None,
) -> StrategyEvaluator:
    return StrategyEvaluator(
        strategy_id=strategy_id,
        feeds=feed_bindings,
        scope="instrument",
        composite_members=None,
        trade_repo=InMemoryTradeRepository(),
        universe_repo=universe_repo,
        feed_store=store,
        event_bus=InMemoryEventBus(),
        run_tracker=FakeRunTracker(),
        strategy_run_repo=strategy_run_repo or InMemoryStrategyRunRepository(),
        clock=FakeClock(NOW),
        evaluator=evaluator,
        uow_factory=FakeUnitOfWorkFactory(),
    )


class TestFeedFrameProjection:
    @pytest.mark.asyncio
    async def test_wide_frame_projects_into_context(self):
        feed_id = uuid.uuid4()
        instrument_id = uuid.uuid4()
        strategy_id = uuid.uuid4()

        store = InMemoryFeedStore()
        await store.put_latest(feed_id, _wide_rows(instrument_id, 107.5), NOW)

        universe_repo = InMemoryStrategyUniverseRepository()
        universe_repo.set_instrument_universe(strategy_id, {instrument_id})

        captured: list[Context] = []

        async def evaluator(ctx: Context, run_id: uuid.UUID) -> None:
            captured.append(ctx)

        service = _make_service(
            strategy_id=strategy_id,
            feed_bindings=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="MARKET_DATA_FEED",
                    channel="ascent.feed.md",
                    is_composite_scoped=False,
                )
            ],
            universe_repo=universe_repo,
            store=store,
            evaluator=evaluator,
        )

        await service._handle_event(
            Event(
                channel="ascent.feed.md",
                payload={
                    "feed_id": str(feed_id),
                    "feed_run_id": str(uuid.uuid4()),
                },
            ),
            satisfied=set(),
            latest_run_ids={},
        )

        assert len(captured) == 1
        ctx = captured[0]
        assert ctx.df.loc[str(instrument_id), ("market_data_feed", "CLOSE")] == 107.5
        assert ctx.universe == frozenset({str(instrument_id)})
        assert ctx.open_only == frozenset()


class TestFeedRunProvenance:
    @pytest.mark.asyncio
    async def test_evaluate_records_feed_runs_on_strategy_run(self):
        """The evaluator must link every feed_run_id it consulted to the
        strategy_run via ``link_feed_runs``. This is the only way the UI can
        later answer "which feed runs produced the data that caused this trade".
        """
        feed_id = uuid.uuid4()
        feed_run_id = uuid.uuid4()
        instrument_id = uuid.uuid4()
        strategy_id = uuid.uuid4()

        store = InMemoryFeedStore()
        await store.put_latest(feed_id, _wide_rows(instrument_id, 99.0), NOW)

        universe_repo = InMemoryStrategyUniverseRepository()
        universe_repo.set_instrument_universe(strategy_id, {instrument_id})

        async def evaluator(ctx: Context, run_id: uuid.UUID) -> None:
            pass

        strategy_runs = InMemoryStrategyRunRepository()
        service = _make_service(
            strategy_id=strategy_id,
            feed_bindings=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="MD",
                    channel="ascent.feed.md",
                    is_composite_scoped=False,
                )
            ],
            universe_repo=universe_repo,
            store=store,
            evaluator=evaluator,
            strategy_run_repo=strategy_runs,
        )

        await service._handle_event(
            Event(
                channel="ascent.feed.md",
                payload={
                    "feed_id": str(feed_id),
                    "feed_run_id": str(feed_run_id),
                },
            ),
            satisfied=set(),
            latest_run_ids={},
        )

        assert len(strategy_runs.links) == 1
        strategy_run_id, feed_run_ids, trigger_feed_id = strategy_runs.links[0]
        assert feed_run_ids == {feed_id: feed_run_id}
        assert trigger_feed_id == feed_id


class TestNoopEvaluation:
    @pytest.mark.asyncio
    async def test_required_feed_missing_does_not_evaluate(self):
        feed_id = uuid.uuid4()
        captured: list = []

        async def evaluator(ctx, run_id):
            captured.append(ctx)

        service = _make_service(
            strategy_id=uuid.uuid4(),
            feed_bindings=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="X",
                    channel="ascent.feed.x",
                    is_composite_scoped=False,
                )
            ],
            universe_repo=InMemoryStrategyUniverseRepository(),
            store=InMemoryFeedStore(),
            evaluator=evaluator,
        )

        await service._handle_event(
            Event(channel="ascent.feed.other", payload={"feed_id": str(uuid.uuid4())}),
            satisfied=set(),
            latest_run_ids={},
        )
        assert captured == []
