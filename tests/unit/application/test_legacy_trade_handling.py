"""Regression tests for legacy trades with NULL ``leg.entry_order_id``."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor, OrderReconciler
from ascent.domain import (
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    PositionType,
    Trade,
    TradeLeg,
    TradeState,
)
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import (
    FakeExchange,
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _legacy_trade_with_unlinked_leg(
    trade_repo: InMemoryTradeRepository,
    order_repo: InMemoryOrderRepository,
    exchange_id: uuid.UUID,
) -> tuple[Trade, Order, uuid.UUID]:
    leg_id = uuid.uuid4()
    leg = TradeLeg(
        id=leg_id,
        instrument_id=uuid.uuid4(),
        direction=PositionType.LONG,
        quantity=1.0,
        entry_order=None,
    )
    trade = Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        state=TradeState.OPENING,
        is_paper=True,
        legs=(leg,),
        entry_at=NOW,
    )
    trade_repo.add(trade)

    order = Order(
        id=uuid.uuid4(),
        state=OrderState.SUBMITTED,
        side=OrderSide.BUY,
        instrument_id=leg.instrument_id,
        quantity=1.0,
        price=100.0,
    )
    order_repo.add(order, trade_id=trade.id, leg_id=leg_id, exchange_id=exchange_id)
    return trade, order, leg_id


@pytest.mark.asyncio
async def test_fill_processor_drops_event_when_order_not_on_trade():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    uow_factory = FakeUnitOfWorkFactory()
    trade, order, _ = _legacy_trade_with_unlinked_leg(
        trade_repo, order_repo, exchange_id=uuid.uuid4()
    )

    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )

    await processor.process(
        trade_id=trade.id,
        event=FillEvent(order_id=order.id, state=OrderState.FILLED),
        now=NOW,
    )

    assert (await trade_repo.get(None, trade.id)).state == TradeState.OPENING
    assert bus.published == []


@pytest.mark.asyncio
async def test_reconciler_heals_missing_entry_order_linkage():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    uow_factory = FakeUnitOfWorkFactory()
    exchange_id = uuid.uuid4()
    trade, order, leg_id = _legacy_trade_with_unlinked_leg(
        trade_repo, order_repo, exchange_id=exchange_id
    )
    await order_repo.set_external_id(None, order.id, "EX-LEGACY")

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-LEGACY",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.0,
        )
    )

    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )
    reconciler = OrderReconciler(
        order_repo=order_repo,
        fill_processor=processor,
        trade_repo=trade_repo,
        uow_factory=uow_factory,
    )

    count = await reconciler.reconcile(exchange=exchange, exchange_id=exchange_id, now=NOW)
    assert count == 1

    healed = await trade_repo.get(None, trade.id)
    assert healed.legs[0].entry_order is not None
    assert healed.legs[0].entry_order.id == order.id
    assert healed.state == TradeState.OPEN


@pytest.mark.asyncio
async def test_reconciler_without_trade_repo_does_not_heal_but_still_drops_safely():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    uow_factory = FakeUnitOfWorkFactory()
    exchange_id = uuid.uuid4()
    _, order, _ = _legacy_trade_with_unlinked_leg(trade_repo, order_repo, exchange_id=exchange_id)
    await order_repo.set_external_id(None, order.id, "EX-LEGACY")

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-LEGACY",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.0,
        )
    )

    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )
    reconciler = OrderReconciler(
        order_repo=order_repo,
        fill_processor=processor,
        uow_factory=uow_factory,
    )
    count = await reconciler.reconcile(exchange=exchange, exchange_id=exchange_id, now=NOW)
    assert count == 1
