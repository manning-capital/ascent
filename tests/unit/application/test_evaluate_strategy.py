"""StrategyEvaluator tests — cover the wide-format feed frame flow."""

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
    InMemoryStrategyUniverseRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _wide_rows(instrument_id: uuid.UUID, price: float) -> pd.DataFrame:
    return pd.DataFrame([{"instrument_id": str(instrument_id), "CLOSE": price}])


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

        service = StrategyEvaluator(
            strategy_id=strategy_id,
            feeds=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="MARKET_DATA_FEED",
                    channel="ascent.feed.md",
                    is_composite_scoped=False,
                )
            ],
            scope="instrument",
            composite_members=None,
            trade_repo=InMemoryTradeRepository(),
            universe_repo=universe_repo,
            feed_store=store,
            event_bus=InMemoryEventBus(),
            run_tracker=FakeRunTracker(),
            clock=FakeClock(NOW),
            evaluator=evaluator,
            uow_factory=FakeUnitOfWorkFactory(),
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


class TestNoopEvaluation:
    @pytest.mark.asyncio
    async def test_required_feed_missing_does_not_evaluate(self):
        feed_id = uuid.uuid4()
        captured: list = []

        async def evaluator(ctx, run_id):
            captured.append(ctx)

        service = StrategyEvaluator(
            strategy_id=uuid.uuid4(),
            feeds=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="X",
                    channel="ascent.feed.x",
                    is_composite_scoped=False,
                )
            ],
            scope="instrument",
            composite_members=None,
            trade_repo=InMemoryTradeRepository(),
            universe_repo=InMemoryStrategyUniverseRepository(),
            feed_store=InMemoryFeedStore(),
            event_bus=InMemoryEventBus(),
            run_tracker=FakeRunTracker(),
            clock=FakeClock(NOW),
            evaluator=evaluator,
            uow_factory=FakeUnitOfWorkFactory(),
        )

        await service._handle_event(
            Event(channel="ascent.feed.other", payload={"feed_id": str(uuid.uuid4())}),
            satisfied=set(),
            latest_run_ids={},
        )
        assert captured == []
