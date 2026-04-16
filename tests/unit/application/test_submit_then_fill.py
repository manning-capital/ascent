"""End-to-end regression: submit → fill must not raise "Order not on trade".

The bug: ``TradeRouter.submit`` created Order rows and set ``Order.trade_leg_id``
pointing at the leg, but never linked the reverse side (``TradeLeg.entry_order_id``).
So when ``FillProcessor.process`` reloaded the trade and the state machine
searched ``leg.entry_order`` for the fill's order id, nothing matched and every
entry fill raised ``ValueError: Order X is not on trade Y``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.domain import FillEvent, OrderState, TradeState
from tests.fakes import (
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_submit_then_fill_entry_closes_trade_to_open():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[ExchangeBinding(exchange_id=uuid.uuid4(), channel="ex.test")],
        is_paper=True,
    )
    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)

    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)

    # After submit, the leg must carry a reference to the entry order.
    trade = await trade_repo.get(draft.trade_id)
    assert len(trade.legs) == 1
    assert trade.legs[0].entry_order is not None, (
        "TradeLeg.entry_order was not linked after router.submit — "
        "fill lookup will fail with 'Order not on trade'."
    )
    order_id = trade.legs[0].entry_order.id

    # Now simulate the fill arriving from the exchange. This was the path that
    # raised ValueError before the fix.
    await processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=order_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=100.0,
        ),
        now=NOW,
    )

    updated = await trade_repo.get(draft.trade_id)
    assert updated.state == TradeState.OPEN
    assert updated.legs[0].entry_price == 100.0


@pytest.mark.asyncio
async def test_submit_then_close_then_fill_exit_closes_trade():
    """Full happy-path lifecycle: submit → entry fill → close → exit fill."""
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[ExchangeBinding(exchange_id=uuid.uuid4(), channel="ex.test")],
        is_paper=True,
    )
    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)

    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    trade = await trade_repo.get(draft.trade_id)
    entry_order_id = trade.legs[0].entry_order.id

    # Entry fill → OPEN.
    await processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_order_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=100.0,
        ),
        now=NOW,
    )
    assert (await trade_repo.get(draft.trade_id)).state == TradeState.OPEN

    # Close → CLOSING, exit order created and linked.
    await router.close(trade_id=draft.trade_id, now=NOW, close_reason="TAKE_PROFIT")
    trade = await trade_repo.get(draft.trade_id)
    assert trade.state == TradeState.CLOSING
    assert trade.legs[0].exit_order is not None
    exit_order_id = trade.legs[0].exit_order.id

    # Exit fill → CLOSED with PnL.
    await processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=exit_order_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=110.0,
        ),
        now=NOW,
    )
    final = await trade_repo.get(draft.trade_id)
    assert final.state == TradeState.CLOSED
    assert final.total_realized_pnl == 10.0  # (110 - 100) * 1
