"""Startup reconciliation scenarios.

When the engine restarts, it asks the exchange what happened to each stale
order and feeds the answer back through :class:`FillProcessor`. The point:
one code path drives both live fills and reconciliation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import OrderReconciler
from ascent.domain import TradeState
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import FakeExchange

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_reconciliation_applies_filled_status_from_exchange(scenario):
    # Submit opens trade; the reconciler will later see the exchange has filled it.
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_order = (await scenario.trade_repo.get(draft.trade_id)).legs[0].entry_order
    # The tracker usually stamps external_order_id after ack; simulate that here.
    external_id = "EX-123"
    await scenario.order_repo.set_external_id(entry_order.id, external_id)

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id=external_id,
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.75,
        )
    )

    reconciler = OrderReconciler(order_repo=scenario.order_repo, fill_processor=scenario.processor)
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 1

    trade = await scenario.trade_repo.get(draft.trade_id)
    assert trade.state == TradeState.OPEN
    assert trade.legs[0].entry_price == 99.75


@pytest.mark.asyncio
async def test_reconciliation_cancels_orders_exchange_has_no_record_of(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_order = (await scenario.trade_repo.get(draft.trade_id)).legs[0].entry_order
    await scenario.order_repo.set_external_id(entry_order.id, "EX-MISSING")

    exchange = FakeExchange()  # open_orders is empty → get_order_status returns NOT_FOUND

    reconciler = OrderReconciler(order_repo=scenario.order_repo, fill_processor=scenario.processor)
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 1
    trade = await scenario.trade_repo.get(draft.trade_id)
    assert trade.state == TradeState.CANCELLED


@pytest.mark.asyncio
async def test_reconciliation_no_stale_orders_is_noop(scenario):
    exchange = FakeExchange()
    reconciler = OrderReconciler(order_repo=scenario.order_repo, fill_processor=scenario.processor)
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 0
