"""TradeRouter use-case tests with in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application.route_trade import (
    CompositeSpec,
    ExchangeBinding,
    TradeRouter,
)
from ascent.domain import Direction, TradeState
from tests.fakes import (
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _router():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    exchange_id = uuid.uuid4()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[
            ExchangeBinding(exchange_id=exchange_id, channel=f"ascent.exchange.{exchange_id}")
        ],
        is_paper=True,
    )
    return router, trade_repo, order_repo, bus, exchange_id


class TestSubmitInstrument:
    @pytest.mark.asyncio
    async def test_submit_creates_trade_leg_and_order(self):
        router, trade_repo, order_repo, bus, exchange_id = _router()
        instrument_id = uuid.uuid4()

        draft = await router.submit(
            side="BUY",
            target_id=instrument_id,
            quantity=2.0,
            now=NOW,
        )

        assert draft.state == TradeState.OPENING
        trade = await trade_repo.get(draft.trade_id)
        assert trade.state == TradeState.OPENING
        assert len(trade.legs) == 1
        assert trade.legs[0].instrument_id == instrument_id
        assert trade.legs[0].direction == Direction.LONG

        order_events = [e for e in bus.published if "order" in e.payload]
        assert len(order_events) == 1
        order_event = order_events[0]
        assert order_event.channel == f"ascent.exchange.{exchange_id}"
        assert order_event.payload["action"] == "submit_order"

        ui_events = [e for e in bus.published if e.channel == "ascent.trades.updates"]
        assert len(ui_events) == 1
        assert ui_events[0].payload == {
            "event": "trade_created",
            "trade_id": str(trade.id),
        }


class TestSubmitComposite:
    @pytest.mark.asyncio
    async def test_composite_first_leg_long_rest_short_on_buy(self):
        router, trade_repo, _, _, _ = _router()
        inst_a, inst_b, inst_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        comp_id = uuid.uuid4()
        draft = await router.submit(
            side="BUY",
            target_id=comp_id,
            scope="composite",
            quantity=1.0,
            now=NOW,
            composite=CompositeSpec(
                composite_id=comp_id,
                ordered_instrument_ids=[inst_a, inst_b, inst_c],
            ),
        )
        trade = await trade_repo.get(draft.trade_id)
        assert [leg.direction for leg in trade.legs] == [
            Direction.LONG,
            Direction.SHORT,
            Direction.SHORT,
        ]

    @pytest.mark.asyncio
    async def test_multi_leg_published_order_quantities_match_specs(self):
        """Regression: an earlier version looked up ``quantity`` via nested
        ``next()`` generators, which caused ``RuntimeError: coroutine raised
        StopIteration`` under PEP 479 and also risked mismatches if trade legs
        ever diverged from specs. Assert each published order's quantity lines
        up with the corresponding leg.
        """
        router, _, _, bus, exchange_id = _router()
        inst_a, inst_b = uuid.uuid4(), uuid.uuid4()
        comp_id = uuid.uuid4()
        await router.submit(
            side="BUY",
            target_id=comp_id,
            scope="composite",
            quantity=2.5,
            now=NOW,
            composite=CompositeSpec(
                composite_id=comp_id,
                ordered_instrument_ids=[inst_a, inst_b],
            ),
        )
        order_events = [e for e in bus.published if e.channel == f"ascent.exchange.{exchange_id}"]
        assert len(order_events) == 2
        for event in order_events:
            payload = event.payload
            assert payload["order"]["quantity"] == 2.5
            assert payload["order"]["from_asset_symbol"] in (str(inst_a), str(inst_b))


class TestClose:
    @pytest.mark.asyncio
    async def test_close_requires_open_state(self):
        router, _, _, _, _ = _router()
        # Submit → OPENING, then try to close — should fail.
        draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
        with pytest.raises(ValueError, match="not OPEN"):
            await router.close(trade_id=draft.trade_id, now=NOW)

    @pytest.mark.asyncio
    async def test_close_persists_close_reason(self):
        """Regression: strategies pass ``close_reason`` through close_trade; the
        router must accept it and thread it to the repo."""
        from ascent.domain import TradeState

        router, trade_repo, _, _, _ = _router()
        draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
        # Manually flip to OPEN so close is allowed.
        await trade_repo.set_state(draft.trade_id, new_state=TradeState.OPEN, at=NOW)

        await router.close(trade_id=draft.trade_id, now=NOW, close_reason="TAKE_PROFIT")

        assert trade_repo.close_reasons[draft.trade_id] == "TAKE_PROFIT"
