"""Regression tests for legacy trades with NULL ``leg.entry_order_id``.

Before ``TradeRouter.submit`` linked the leg back to its entry order, trades
could be persisted where the forward FK (``Order.trade_leg_id`` → leg) was
set but the reverse FK (``TradeLeg.entry_order_id`` → order) was NULL. When
those trades arrived at the fill path, the state machine couldn't find the
order on the trade and raised ``ValueError`` — which crashed the service
task. These tests pin down two defences:

1. ``FillProcessor.process`` logs and drops on location failure rather than
   propagating — one bad event never tears down the whole loop.
2. ``OrderReconciler`` actively heals the linkage when ``trade_repo`` is
   wired in — legacy trades self-fix on the first reconciliation pass.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor, OrderReconciler
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
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import (
    FakeExchange,
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
    """Build a trade that matches the legacy on-disk shape: Order has
    ``trade_leg_id`` set but ``TradeLeg.entry_order`` is None.
    """
    leg_id = uuid.uuid4()
    leg = TradeLeg(
        id=leg_id,
        instrument_id=uuid.uuid4(),
        direction=Direction.LONG,
        quantity=1.0,
        entry_order=None,  # <-- the legacy state we're guarding against
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

    order = Order(
        id=uuid.uuid4(),
        state=OrderState.SUBMITTED,
        side=OrderSide.BUY,
        instrument_id=leg.instrument_id,
        quantity=1.0,
        price=100.0,
    )
    # Mirror SQL adapter: order row carries the forward link to the leg.
    order_repo.add(order, trade_id=trade.id, leg_id=leg_id, exchange_id=exchange_id)
    return trade, order, leg_id


@pytest.mark.asyncio
async def test_fill_processor_drops_event_when_order_not_on_trade():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    trade, order, _ = _legacy_trade_with_unlinked_leg(
        trade_repo, order_repo, exchange_id=uuid.uuid4()
    )

    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)

    # Must not raise — the service loop above depends on this staying alive.
    await processor.process(
        trade_id=trade.id,
        event=FillEvent(order_id=order.id, state=OrderState.FILLED),
        now=NOW,
    )

    # Trade stays untouched (no state change, no UI notification).
    assert (await trade_repo.get(trade.id)).state == TradeState.OPENING
    assert bus.published == []


@pytest.mark.asyncio
async def test_reconciler_heals_missing_entry_order_linkage():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    exchange_id = uuid.uuid4()
    trade, order, leg_id = _legacy_trade_with_unlinked_leg(
        trade_repo, order_repo, exchange_id=exchange_id
    )
    # Give the order an external id so the reconciler can fetch its status.
    await order_repo.set_external_id(order.id, "EX-LEGACY")

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-LEGACY",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.0,
        )
    )

    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)
    reconciler = OrderReconciler(
        order_repo=order_repo,
        fill_processor=processor,
        trade_repo=trade_repo,
    )

    count = await reconciler.reconcile(exchange=exchange, exchange_id=exchange_id, now=NOW)
    assert count == 1

    healed = await trade_repo.get(trade.id)
    # The linkage was backfilled …
    assert healed.legs[0].entry_order is not None
    assert healed.legs[0].entry_order.id == order.id
    # … and the fill then landed cleanly, flipping the trade to OPEN.
    assert healed.state == TradeState.OPEN


@pytest.mark.asyncio
async def test_reconciler_without_trade_repo_does_not_heal_but_still_drops_safely():
    """Belt-and-suspenders: even if the Runner forgot to pass trade_repo to
    the reconciler, the service must not crash on legacy trades.
    """
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    exchange_id = uuid.uuid4()
    _, order, _ = _legacy_trade_with_unlinked_leg(trade_repo, order_repo, exchange_id=exchange_id)
    await order_repo.set_external_id(order.id, "EX-LEGACY")

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-LEGACY",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.0,
        )
    )

    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)
    # No trade_repo → no healing. Must still return normally.
    reconciler = OrderReconciler(order_repo=order_repo, fill_processor=processor)
    count = await reconciler.reconcile(exchange=exchange, exchange_id=exchange_id, now=NOW)
    assert count == 1  # event was dispatched, even if dropped downstream
