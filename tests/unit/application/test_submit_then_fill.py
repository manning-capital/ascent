"""End-to-end regression: submit → fill must not raise "Order not on trade"."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.domain import FillEvent, OrderState, TradeState
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _wire():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow_factory = FakeUnitOfWorkFactory()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=uuid.uuid4(), channel="ex.test")],
        is_paper=True,
    )
    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )
    return router, trade_repo, order_repo, bus, processor


@pytest.mark.asyncio
async def test_submit_then_fill_entry_closes_trade_to_open():
    router, trade_repo, _, _, processor = _wire()

    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)

    trade = await trade_repo.get(None, draft.trade_id)
    assert len(trade.legs) == 1
    assert trade.legs[0].entry_order is not None
    order_id = trade.legs[0].entry_order.id

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

    updated = await trade_repo.get(None, draft.trade_id)
    assert updated.state == TradeState.OPEN
    assert updated.legs[0].entry_price == 100.0


@pytest.mark.asyncio
async def test_submit_then_close_then_fill_exit_closes_trade():
    """Full happy-path lifecycle: submit → entry fill → close → exit fill."""
    router, trade_repo, _, _, processor = _wire()

    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    trade = await trade_repo.get(None, draft.trade_id)
    entry_order_id = trade.legs[0].entry_order.id

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
    assert (await trade_repo.get(None, draft.trade_id)).state == TradeState.OPEN

    await router.close(trade_id=draft.trade_id, now=NOW, close_reason="TAKE_PROFIT")
    trade = await trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.CLOSING
    assert trade.legs[0].exit_order is not None
    exit_order_id = trade.legs[0].exit_order.id

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
    final = await trade_repo.get(None, draft.trade_id)
    assert final.state == TradeState.CLOSED
    assert final.total_realized_pnl == 10.0
