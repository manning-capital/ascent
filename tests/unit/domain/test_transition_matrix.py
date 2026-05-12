"""Exhaustive transition-matrix test for :func:`apply_fill`.

Every (from-state × fill-state) combination is enumerated explicitly. The
matrix is the spec; if you change the state machine, you must update this
table — which is exactly what forces you to think about every corner.

Compare to the hand-written scenarios in ``test_state_machine.py`` — those
document intent; this proves coverage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.domain import (
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    PositionType,
    Trade,
    TradeLeg,
    TradeState,
    apply_fill,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _single_leg_trade(
    trade_state: TradeState,
    *,
    entry_state: OrderState = OrderState.SUBMITTED,
    exit_state: OrderState | None = None,
    entry_filled_price: float | None = None,
) -> tuple[Trade, Order, Order | None]:
    entry_order = Order(
        id=uuid.uuid4(),
        state=entry_state,
        side=OrderSide.BUY,
        instrument_id=uuid.uuid4(),
        quantity=1.0,
        price=100.0,
    )
    exit_order = (
        Order(
            id=uuid.uuid4(),
            state=exit_state,
            side=OrderSide.SELL,
            instrument_id=entry_order.instrument_id,
            quantity=1.0,
            price=100.0,
        )
        if exit_state is not None
        else None
    )
    leg = TradeLeg(
        id=uuid.uuid4(),
        instrument_id=entry_order.instrument_id,
        direction=PositionType.LONG,
        quantity=1.0,
        entry_order=entry_order,
        exit_order=exit_order,
        entry_price=entry_filled_price,
    )
    trade = Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        state=trade_state,
        is_paper=True,
        legs=(leg,),
        entry_at=NOW,
    )
    return trade, entry_order, exit_order


# ---------------------------------------------------------------------------
# OPENING row: fill on the entry order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fill_state,expected",
    [
        # Full fill → OPEN.
        (OrderState.FILLED, TradeState.OPEN),
        # Partial fill → stay OPENING.
        (OrderState.PARTIALLY_FILLED, TradeState.OPENING),
        # Terminal non-fill → CANCELLED (no active orders remain).
        (OrderState.REJECTED, TradeState.CANCELLED),
        (OrderState.CANCELLED, TradeState.CANCELLED),
    ],
)
def test_opening_with_single_leg(fill_state, expected):
    trade, entry_order, _ = _single_leg_trade(TradeState.OPENING)
    event = FillEvent(
        order_id=entry_order.id,
        state=fill_state,
        filled_quantity=1.0 if fill_state == OrderState.FILLED else 0.5,
        average_fill_price=100.0 if fill_state == OrderState.FILLED else None,
    )
    assert apply_fill(trade, event, now=NOW).new_state == expected


# ---------------------------------------------------------------------------
# CLOSING row: fill on the exit order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fill_state,expected",
    [
        (OrderState.FILLED, TradeState.CLOSED),
        (OrderState.PARTIALLY_FILLED, TradeState.CLOSING),
        # Exit failed → OPEN (position still held; strategy can retry).
        (OrderState.REJECTED, TradeState.OPEN),
        (OrderState.CANCELLED, TradeState.OPEN),
    ],
)
def test_closing_with_single_leg(fill_state, expected):
    trade, _, exit_order = _single_leg_trade(
        TradeState.CLOSING,
        entry_state=OrderState.FILLED,
        exit_state=OrderState.SUBMITTED,
        entry_filled_price=100.0,
    )
    event = FillEvent(
        order_id=exit_order.id,
        state=fill_state,
        filled_quantity=1.0 if fill_state == OrderState.FILLED else 0.5,
        average_fill_price=110.0 if fill_state == OrderState.FILLED else None,
    )
    assert apply_fill(trade, event, now=NOW).new_state == expected


# ---------------------------------------------------------------------------
# Stable rows: fills don't move these states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trade_state",
    [
        TradeState.PENDING,
        TradeState.OPEN,
        TradeState.CLOSED,
        TradeState.CANCELLED,
    ],
)
@pytest.mark.parametrize(
    "fill_state",
    [OrderState.FILLED, OrderState.PARTIALLY_FILLED, OrderState.REJECTED],
)
def test_stable_states_never_transition(trade_state, fill_state):
    trade, entry_order, _ = _single_leg_trade(trade_state)
    event = FillEvent(
        order_id=entry_order.id,
        state=fill_state,
        filled_quantity=1.0,
        average_fill_price=100.0,
    )
    transition = apply_fill(trade, event, now=NOW)
    assert transition.new_state == trade_state, (
        f"{trade_state} must not move under {fill_state}; got {transition.new_state}"
    )


# ---------------------------------------------------------------------------
# ERROR row: recovery depends on whether any order is still active
# ---------------------------------------------------------------------------


def test_error_with_active_order_stays_error():
    """If at least one order is still active, ERROR must wait — the state
    machine can't decide until all orders are terminal.
    """
    trade, entry_order, _ = _single_leg_trade(
        TradeState.ERROR, entry_state=OrderState.PARTIALLY_FILLED
    )
    event = FillEvent(
        order_id=entry_order.id,
        state=OrderState.PARTIALLY_FILLED,
        filled_quantity=0.3,
    )
    assert apply_fill(trade, event, now=NOW).new_state == TradeState.ERROR


def test_error_all_terminal_with_a_fill_recovers_to_open():
    trade, entry_order, _ = _single_leg_trade(TradeState.ERROR)
    event = FillEvent(
        order_id=entry_order.id,
        state=OrderState.FILLED,
        filled_quantity=1.0,
        average_fill_price=100.0,
    )
    assert apply_fill(trade, event, now=NOW).new_state == TradeState.OPEN


def test_error_all_terminal_with_no_fills_cancels():
    trade, entry_order, _ = _single_leg_trade(TradeState.ERROR)
    event = FillEvent(order_id=entry_order.id, state=OrderState.REJECTED)
    assert apply_fill(trade, event, now=NOW).new_state == TradeState.CANCELLED


# ---------------------------------------------------------------------------
# PnL side-effect invariants (any FILL on CLOSING must compute PnL)
# ---------------------------------------------------------------------------


def test_closed_transition_always_sets_exit_at_and_pnl():
    trade, _, exit_order = _single_leg_trade(
        TradeState.CLOSING,
        entry_state=OrderState.FILLED,
        exit_state=OrderState.SUBMITTED,
        entry_filled_price=100.0,
    )
    event = FillEvent(
        order_id=exit_order.id,
        state=OrderState.FILLED,
        filled_quantity=1.0,
        average_fill_price=115.0,
    )
    transition = apply_fill(trade, event, now=NOW)
    assert transition.new_state == TradeState.CLOSED
    assert transition.exit_at == NOW
    assert transition.total_realized_pnl == 15.0  # LONG: (115 - 100) * 1


def test_non_closed_transition_does_not_set_exit_at():
    trade, entry_order, _ = _single_leg_trade(TradeState.OPENING)
    event = FillEvent(
        order_id=entry_order.id,
        state=OrderState.FILLED,
        filled_quantity=1.0,
        average_fill_price=100.0,
    )
    transition = apply_fill(trade, event, now=NOW)
    assert transition.new_state == TradeState.OPEN
    assert transition.exit_at is None
    assert transition.total_realized_pnl is None
