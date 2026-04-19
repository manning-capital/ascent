"""Process-fill use-case tests with in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor
from ascent.domain import (
    Direction,
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    Trade,
    TradeLeg,
    TradeState,
)
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def wiring():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    uow_factory = FakeUnitOfWorkFactory()
    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )
    return trade_repo, order_repo, bus, processor


def _build_opening_trade(trade_repo, order_repo):
    entry_order = Order(
        id=uuid.uuid4(),
        state=OrderState.SUBMITTED,
        side=OrderSide.BUY,
        instrument_id=uuid.uuid4(),
        quantity=1.0,
        price=100.0,
    )
    leg = TradeLeg(
        id=uuid.uuid4(),
        instrument_id=entry_order.instrument_id,
        direction=Direction.LONG,
        quantity=1.0,
        entry_order=entry_order,
    )
    trade = Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        state=TradeState.OPENING,
        is_paper=True,
        legs=(leg,),
        entry_at=NOW,
    )
    trade_repo.add(trade)
    order_repo.add(entry_order, trade_id=trade.id, leg_id=leg.id, exchange_id=uuid.uuid4())
    return trade, entry_order, leg


class TestProcessFill:
    @pytest.mark.asyncio
    async def test_entry_fill_moves_trade_to_open(self, wiring):
        trade_repo, order_repo, bus, processor = wiring
        trade, entry_order, _ = _build_opening_trade(trade_repo, order_repo)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry_order.id,
                state=OrderState.FILLED,
                filled_quantity=1.0,
                average_fill_price=105.0,
            ),
            now=NOW,
        )

        updated = await trade_repo.get(None, trade.id)
        assert updated.state == TradeState.OPEN
        assert updated.legs[0].entry_price == 105.0

        stored_order = await order_repo.get(None, entry_order.id)
        assert stored_order.state == OrderState.FILLED
        assert stored_order.filled_quantity == 1.0
        assert stored_order.average_fill_price == 105.0

        assert bus.published[-1].channel == "ascent.trades.updates"
        assert bus.published[-1].payload["event"] == "trade_updated"

    @pytest.mark.asyncio
    async def test_partial_fill_keeps_opening(self, wiring):
        trade_repo, order_repo, _, processor = wiring
        trade, order, _ = _build_opening_trade(trade_repo, order_repo)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=order.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.4,
                average_fill_price=103.0,
            ),
            now=NOW,
        )
        updated = await trade_repo.get(None, trade.id)
        assert updated.state == TradeState.OPENING
        assert updated.legs[0].entry_price is None

    @pytest.mark.asyncio
    async def test_unknown_trade_is_dropped(self, wiring):
        _, _, bus, processor = wiring
        await processor.process(
            trade_id=uuid.uuid4(),
            event=FillEvent(order_id=uuid.uuid4(), state=OrderState.FILLED),
            now=NOW,
        )
        assert bus.published == []
