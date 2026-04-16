"""StrategyEvaluator tests — cover attribute resolution + end-to-end evaluate flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pandas as pd
import pytest

from ascent.application.evaluate_strategy import FeedBinding, StrategyEvaluator
from ascent.application.trigger import StrategyFeedSpec
from ascent.ports import Event
from tests.fakes import (
    FakeClock,
    FakeRunTracker,
    InMemoryEventBus,
    InMemoryFeedStore,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _eav_rows(instrument_id: uuid.UUID, close_attr: uuid.UUID, price: float) -> pd.DataFrame:
    """Build a feed DataFrame in the shape the feed publisher emits."""
    return pd.DataFrame(
        [
            {
                "timestamp": NOW.isoformat(),
                "instrument_id": str(instrument_id),
                # This is the bug path — attribute_id arrives as a STRING UUID after Redis round-trip.
                "attribute_id": str(close_attr),
                "attribute_value": price,
            }
        ]
    )


class TestAttributeNameResolution:
    """Regression tests: the strategy context must resolve attribute_id → name.

    Bug: previously the context builder required ``attribute_name`` to exist
    but nothing was populating it, producing ``KeyError('market_data_feed',
    'close')`` inside the strategy's ``evaluate`` body.
    """

    @pytest.mark.asyncio
    async def test_attribute_id_strings_resolve_to_names(self):
        feed_id = uuid.uuid4()
        close_attr = uuid.uuid4()
        instrument_id = uuid.uuid4()

        store = InMemoryFeedStore()
        await store.put_latest(feed_id, _eav_rows(instrument_id, close_attr, 107.5), NOW)

        captured: list[pd.DataFrame] = []

        async def evaluator(ctx: pd.DataFrame, run_id: uuid.UUID) -> None:
            captured.append(ctx)

        service = StrategyEvaluator(
            strategy_id=uuid.uuid4(),
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
            feed_store=store,
            event_bus=InMemoryEventBus(),
            run_tracker=FakeRunTracker(),
            clock=FakeClock(NOW),
            evaluator=evaluator,
            attribute_map={close_attr: "close"},
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
        # This is the exact column access that was breaking in the real strategy.
        assert ctx.loc[str(instrument_id), ("market_data_feed", "close")] == 107.5

    @pytest.mark.asyncio
    async def test_unknown_attribute_falls_back_to_id_string(self):
        """An attribute id missing from the map should survive as its string
        id — it just ends up under a column named after the id.
        """
        feed_id = uuid.uuid4()
        unknown_attr = uuid.uuid4()
        instrument_id = uuid.uuid4()
        store = InMemoryFeedStore()
        await store.put_latest(feed_id, _eav_rows(instrument_id, unknown_attr, 1.0), NOW)

        captured: list[pd.DataFrame] = []

        async def evaluator(ctx, run_id):
            captured.append(ctx)

        service = StrategyEvaluator(
            strategy_id=uuid.uuid4(),
            feeds=[
                FeedBinding(
                    spec=StrategyFeedSpec(feed_id=feed_id, is_required=True),
                    feed_ref="MD",
                    channel="ascent.feed.md",
                    is_composite_scoped=False,
                )
            ],
            scope="instrument",
            composite_members=None,
            trade_repo=InMemoryTradeRepository(),
            feed_store=store,
            event_bus=InMemoryEventBus(),
            run_tracker=FakeRunTracker(),
            clock=FakeClock(NOW),
            evaluator=evaluator,
            attribute_map={},  # empty — everything is unknown
        )

        await service._handle_event(
            Event(
                channel="ascent.feed.md",
                payload={"feed_id": str(feed_id)},
            ),
            satisfied=set(),
            latest_run_ids={},
        )

        ctx = captured[0]
        # Unknown attribute survives as its id string rather than crashing.
        assert ("md", str(unknown_attr)) in ctx.columns


class TestNoopEvaluation:
    """If no required feed has data yet, evaluate should not fire."""

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
            feed_store=InMemoryFeedStore(),
            event_bus=InMemoryEventBus(),
            run_tracker=FakeRunTracker(),
            clock=FakeClock(NOW),
            evaluator=evaluator,
        )

        # Fire an event for an UNRELATED feed id — required feed not satisfied.
        await service._handle_event(
            Event(channel="ascent.feed.other", payload={"feed_id": str(uuid.uuid4())}),
            satisfied=set(),
            latest_run_ids={},
        )
        assert captured == []
