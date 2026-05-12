"""Startup reconciliation scenarios."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import OrderReconciler
from ascent.application.reconcile_orders import ORPHAN_REASON
from ascent.domain import FillEvent, OrderState, TradeState
from ascent.exchanges.base import BalanceEntry, OrderStatusResponse
from tests.fakes import FakeExchange

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_reconciliation_applies_filled_status_from_exchange(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_order = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order
    external_id = "EX-123"
    await scenario.order_repo.set_external_id(None, entry_order.id, external_id)

    exchange = FakeExchange()
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id=external_id,
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.75,
        )
    )

    reconciler = OrderReconciler(
        order_repo=scenario.order_repo,
        fill_processor=scenario.processor,
        uow_factory=scenario.uow_factory,
    )
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 1

    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.OPEN
    assert trade.legs[0].entry_price == 99.75


@pytest.mark.asyncio
async def test_reconciliation_cancels_orders_exchange_has_no_record_of(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_order = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order
    await scenario.order_repo.set_external_id(None, entry_order.id, "EX-MISSING")

    exchange = FakeExchange()

    reconciler = OrderReconciler(
        order_repo=scenario.order_repo,
        fill_processor=scenario.processor,
        uow_factory=scenario.uow_factory,
    )
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 1
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.CANCELLED


@pytest.mark.asyncio
async def test_reconciliation_no_stale_orders_is_noop(scenario):
    exchange = FakeExchange()
    reconciler = OrderReconciler(
        order_repo=scenario.order_repo,
        fill_processor=scenario.processor,
        uow_factory=scenario.uow_factory,
    )
    count = await reconciler.reconcile(exchange=exchange, exchange_id=scenario.exchange_id, now=NOW)
    assert count == 0


# ---------------------------------------------------------------------------
# Phantom-trade sweep
# ---------------------------------------------------------------------------


async def _open_trade_with_filled_entry(
    scenario,
    *,
    side: str,
    quantity: float,
    fill_price: float,
    instrument_id: uuid.UUID | None = None,
):
    """Submit a trade, simulate the entry order filling, return its trade_id.

    Leaves the trade in :class:`TradeState.OPEN` with a filled entry order.
    """
    instrument_id = instrument_id or uuid.uuid4()
    scenario.trade_repo.register_instrument_assets(instrument_id, "BTC", "USD")
    draft = await scenario.router.submit(
        side=side, target_id=instrument_id, quantity=quantity, now=NOW
    )
    entry_order = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order
    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_order.id,
            state=OrderState.FILLED,
            filled_quantity=quantity,
            average_fill_price=fill_price,
        ),
        now=NOW,
    )
    return draft.trade_id


def _reconciler(scenario) -> OrderReconciler:
    return OrderReconciler(
        order_repo=scenario.order_repo,
        fill_processor=scenario.processor,
        uow_factory=scenario.uow_factory,
        trade_repo=scenario.trade_repo,
        event_bus=scenario.bus,
    )


@pytest.mark.asyncio
async def test_sweep_terminates_orphan_open_trade_when_balance_empty(scenario):
    """The user-reported failure mode: trade is OPEN, no active orders, exchange
    has no balance backing it (paper restart wiped state). Sweep terminates."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="BUY", quantity=1.0, fill_price=100.0
    )
    assert (await scenario.trade_repo.get(None, trade_id)).state == TradeState.OPEN

    exchange = FakeExchange()  # balances empty
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    trade = await scenario.trade_repo.get(None, trade_id)
    assert trade.state == TradeState.CANCELLED
    assert scenario.trade_repo.close_reasons[trade_id] == ORPHAN_REASON


@pytest.mark.asyncio
async def test_sweep_leaves_real_position_alone(scenario):
    """Exchange holds the claimed position → sweep is a no-op."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="BUY", quantity=0.5, fill_price=50000.0
    )

    exchange = FakeExchange()
    exchange.balances = [
        BalanceEntry(asset_symbol="BTC", available=0.5, reserved=0.0, total=0.5),
        BalanceEntry(asset_symbol="USD", available=-25000.0, reserved=0.0, total=-25000.0),
    ]
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    assert (await scenario.trade_repo.get(None, trade_id)).state == TradeState.OPEN


@pytest.mark.asyncio
async def test_sweep_handles_short_position_with_negative_balance(scenario):
    """A short position is backed by a negative base-asset balance."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="SELL", quantity=0.25, fill_price=60000.0
    )

    exchange = FakeExchange()
    exchange.balances = [
        BalanceEntry(asset_symbol="BTC", available=-0.25, reserved=0.0, total=-0.25),
        BalanceEntry(asset_symbol="USD", available=15000.0, reserved=0.0, total=15000.0),
    ]
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    assert (await scenario.trade_repo.get(None, trade_id)).state == TradeState.OPEN


@pytest.mark.asyncio
async def test_sweep_terminates_short_when_balance_zero(scenario):
    """Same short position, exchange has no negative balance → phantom."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="SELL", quantity=0.25, fill_price=60000.0
    )

    exchange = FakeExchange()  # empty balances
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    assert (await scenario.trade_repo.get(None, trade_id)).state == TradeState.CANCELLED


@pytest.mark.asyncio
async def test_sweep_terminates_orphan_closing_trade(scenario):
    """The original bug. Trade in CLOSING gets all exit orders cancelled by the
    per-order pass; state machine reverts it to OPEN; sweep then terminates."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="BUY", quantity=1.0, fill_price=100.0
    )
    # Submit exit orders → trade transitions to CLOSING.
    await scenario.router.close(trade_id=trade_id, now=NOW)
    closing_trade = await scenario.trade_repo.get(None, trade_id)
    assert closing_trade.state == TradeState.CLOSING
    exit_order = closing_trade.legs[0].exit_order
    await scenario.order_repo.set_external_id(None, exit_order.id, "EX-EXIT")

    # Simulate the paper-restart scenario: exchange has no record of the exit
    # order and no balance to back the original position.
    exchange = FakeExchange()
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    trade = await scenario.trade_repo.get(None, trade_id)
    # Per-order processing reverted CLOSING → OPEN; sweep then terminates.
    assert trade.state == TradeState.CANCELLED
    assert scenario.trade_repo.close_reasons[trade_id] == ORPHAN_REASON


@pytest.mark.asyncio
async def test_sweep_skips_trade_with_active_orders(scenario):
    """Trades that still have active orders on the exchange must never be
    swept — a strategy is actively working them."""
    instrument_id = uuid.uuid4()
    scenario.trade_repo.register_instrument_assets(instrument_id, "BTC", "USD")
    draft = await scenario.router.submit(side="BUY", target_id=instrument_id, quantity=1.0, now=NOW)
    # Entry order is still SUBMITTED — no fill simulated. Trade is in OPENING.
    assert (await scenario.trade_repo.get(None, draft.trade_id)).state == TradeState.OPENING

    exchange = FakeExchange()  # empty balances
    # The reconciler will see the SUBMITTED order, look it up, get NOT_FOUND,
    # and synthesize a CANCELLED fill — which the state machine routes to
    # CANCELLED for a fresh OPENING trade. That's existing behavior; what we
    # care about here is that the sweep doesn't *also* fire a second time on
    # an already-cancelled trade.
    await _reconciler(scenario).reconcile(
        exchange=exchange, exchange_id=scenario.exchange_id, now=NOW
    )

    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.CANCELLED


@pytest.mark.asyncio
async def test_sweep_publishes_trade_updated_event(scenario):
    """Terminated phantoms should ping the UI via the event bus."""
    trade_id = await _open_trade_with_filled_entry(
        scenario, side="BUY", quantity=1.0, fill_price=100.0
    )
    scenario.bus.published.clear()  # ignore creation/fill events

    await _reconciler(scenario).reconcile(
        exchange=FakeExchange(), exchange_id=scenario.exchange_id, now=NOW
    )

    updates = [
        event.payload
        for event in scenario.bus.published
        if event.payload.get("trade_id") == str(trade_id)
    ]
    assert any(p.get("event") == "trade_updated" for p in updates)
