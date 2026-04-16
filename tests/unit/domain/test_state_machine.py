"""Unit tests for the pure trade state machine.

These tests exercise :mod:`ascent.domain.state_machine` with no I/O — they
verify the decisions the engine should make for every trade-lifecycle
transition we care about.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.domain import (
    Direction,
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    Trade,
    TradeLeg,
    TradeState,
    apply_fill,
    opening_from_orders,
)

NOW = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)


def _order(state: OrderState = OrderState.SUBMITTED, **overrides) -> Order:
    return Order(
        id=overrides.pop("id", uuid.uuid4()),
        state=state,
        side=overrides.pop("side", OrderSide.BUY),
        instrument_id=overrides.pop("instrument_id", uuid.uuid4()),
        quantity=overrides.pop("quantity", 1.0),
        price=overrides.pop("price", 100.0),
        filled_quantity=overrides.pop("filled_quantity", 0.0),
        average_fill_price=overrides.pop("average_fill_price", None),
    )


def _leg(
    entry: Order | None = None,
    exit: Order | None = None,
    direction: Direction = Direction.LONG,
    entry_price: float | None = None,
    quantity: float = 1.0,
) -> TradeLeg:
    return TradeLeg(
        id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        direction=direction,
        quantity=quantity,
        entry_order=entry,
        exit_order=exit,
        entry_price=entry_price,
    )


def _trade(state: TradeState, legs: list[TradeLeg]) -> Trade:
    return Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        state=state,
        is_paper=True,
        legs=tuple(legs),
        entry_at=NOW,
    )


# ---------------------------------------------------------------------------
# opening_from_orders
# ---------------------------------------------------------------------------


class TestOpeningFromOrders:
    def test_all_active_entry_orders_go_opening(self):
        trade = _trade(TradeState.PENDING, [_leg(entry=_order()), _leg(entry=_order())])
        assert opening_from_orders(trade) == TradeState.OPENING

    def test_missing_entry_order_is_error(self):
        trade = _trade(TradeState.PENDING, [_leg(entry=_order()), _leg(entry=None)])
        assert opening_from_orders(trade) == TradeState.ERROR

    def test_rejected_entry_order_is_error(self):
        trade = _trade(TradeState.PENDING, [_leg(entry=_order(OrderState.REJECTED))])
        assert opening_from_orders(trade) == TradeState.ERROR

    def test_trade_with_no_legs_is_error(self):
        trade = _trade(TradeState.PENDING, [])
        assert opening_from_orders(trade) == TradeState.ERROR


# ---------------------------------------------------------------------------
# OPENING trade — fills on entry orders
# ---------------------------------------------------------------------------


class TestOpeningFills:
    def test_all_entries_filled_goes_open(self):
        e1, e2 = _order(), _order()
        trade = _trade(TradeState.OPENING, [_leg(entry=e1), _leg(entry=e2)])

        # First fill — still OPENING.
        t1 = apply_fill(
            trade,
            FillEvent(e1.id, OrderState.FILLED, 1.0, 100.0),
            now=NOW,
        )
        assert t1.new_state == TradeState.OPENING

        # Apply the first transition and fire the second fill.
        trade2 = _trade(
            TradeState.OPENING,
            [
                _leg(entry=_order(OrderState.FILLED, id=e1.id)),
                _leg(entry=e2),
            ],
        )
        t2 = apply_fill(
            trade2,
            FillEvent(e2.id, OrderState.FILLED, 1.0, 200.0),
            now=NOW,
        )
        assert t2.new_state == TradeState.OPEN

    def test_all_entries_resolved_without_fill_goes_cancelled(self):
        e1 = _order()
        trade = _trade(TradeState.OPENING, [_leg(entry=e1)])
        transition = apply_fill(
            trade,
            FillEvent(e1.id, OrderState.REJECTED, 0.0, None),
            now=NOW,
        )
        assert transition.new_state == TradeState.CANCELLED

    def test_partial_fill_keeps_opening(self):
        e1 = _order()
        trade = _trade(TradeState.OPENING, [_leg(entry=e1)])
        transition = apply_fill(
            trade,
            FillEvent(e1.id, OrderState.PARTIALLY_FILLED, 0.5, 100.0),
            now=NOW,
        )
        assert transition.new_state == TradeState.OPENING

    def test_filled_entry_records_entry_price(self):
        e1 = _order()
        trade = _trade(TradeState.OPENING, [_leg(entry=e1, direction=Direction.LONG)])
        transition = apply_fill(
            trade,
            FillEvent(e1.id, OrderState.FILLED, 1.0, 105.5),
            now=NOW,
        )
        assert len(transition.leg_updates) == 1
        assert transition.leg_updates[0].entry_price == 105.5
        assert transition.leg_updates[0].exit_price is None


# ---------------------------------------------------------------------------
# CLOSING trade — fills on exit orders compute PnL
# ---------------------------------------------------------------------------


class TestClosingFills:
    def test_long_exit_fill_computes_pnl(self):
        exit_order = _order(side=OrderSide.SELL)
        leg = _leg(
            entry=_order(OrderState.FILLED),
            exit=exit_order,
            direction=Direction.LONG,
            entry_price=100.0,
            quantity=2.0,
        )
        trade = _trade(TradeState.CLOSING, [leg])

        transition = apply_fill(
            trade,
            FillEvent(exit_order.id, OrderState.FILLED, 2.0, 110.0),
            now=NOW,
        )

        assert transition.new_state == TradeState.CLOSED
        assert transition.exit_at == NOW
        # (110 - 100) * 2 = 20.0
        assert transition.total_realized_pnl == 20.0
        leg_update = transition.leg_updates[0]
        assert leg_update.exit_price == 110.0
        assert leg_update.realized_pnl == 20.0

    def test_short_exit_fill_computes_negative_pnl(self):
        exit_order = _order(side=OrderSide.BUY)
        leg = _leg(
            entry=_order(OrderState.FILLED),
            exit=exit_order,
            direction=Direction.SHORT,
            entry_price=100.0,
            quantity=1.0,
        )
        trade = _trade(TradeState.CLOSING, [leg])

        transition = apply_fill(
            trade,
            FillEvent(exit_order.id, OrderState.FILLED, 1.0, 110.0),
            now=NOW,
        )
        # short: (entry - exit) * qty = -10
        assert transition.new_state == TradeState.CLOSED
        assert transition.total_realized_pnl == -10.0

    def test_closing_reopens_when_all_exits_fail(self):
        xo = _order()
        leg = _leg(
            entry=_order(OrderState.FILLED),
            exit=xo,
            direction=Direction.LONG,
            entry_price=100.0,
        )
        trade = _trade(TradeState.CLOSING, [leg])

        transition = apply_fill(
            trade,
            FillEvent(xo.id, OrderState.REJECTED, 0.0, None),
            now=NOW,
        )
        assert transition.new_state == TradeState.OPEN

    def test_closing_stays_closing_on_partial_fill(self):
        xo = _order()
        leg = _leg(
            entry=_order(OrderState.FILLED),
            exit=xo,
            direction=Direction.LONG,
            entry_price=100.0,
        )
        trade = _trade(TradeState.CLOSING, [leg])

        transition = apply_fill(
            trade,
            FillEvent(xo.id, OrderState.PARTIALLY_FILLED, 0.5, 110.0),
            now=NOW,
        )
        assert transition.new_state == TradeState.CLOSING


# ---------------------------------------------------------------------------
# Terminal states — fills are no-ops on state
# ---------------------------------------------------------------------------


class TestTerminalStates:
    @pytest.mark.parametrize(
        "state", [TradeState.CLOSED, TradeState.CANCELLED, TradeState.OPEN, TradeState.PENDING]
    )
    def test_stable_states_do_not_move_on_fill(self, state):
        order = _order()
        trade = _trade(state, [_leg(entry=order)])
        transition = apply_fill(
            trade,
            FillEvent(order.id, OrderState.FILLED, 1.0, 100.0),
            now=NOW,
        )
        assert transition.new_state == state


# ---------------------------------------------------------------------------
# ERROR recovery
# ---------------------------------------------------------------------------


class TestErrorRecovery:
    def test_error_with_all_entries_filled_recovers_to_open(self):
        e1 = _order(OrderState.FILLED)
        e2 = _order()
        trade = _trade(TradeState.ERROR, [_leg(entry=e1), _leg(entry=e2)])
        transition = apply_fill(
            trade,
            FillEvent(e2.id, OrderState.FILLED, 1.0, 100.0),
            now=NOW,
        )
        assert transition.new_state == TradeState.OPEN

    def test_error_with_no_fills_goes_cancelled(self):
        e1 = _order()
        trade = _trade(TradeState.ERROR, [_leg(entry=e1)])
        transition = apply_fill(
            trade,
            FillEvent(e1.id, OrderState.REJECTED, 0.0, None),
            now=NOW,
        )
        assert transition.new_state == TradeState.CANCELLED


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unknown_order_id_raises(self):
        trade = _trade(TradeState.OPENING, [_leg(entry=_order())])
        with pytest.raises(ValueError, match="not on trade"):
            apply_fill(
                trade,
                FillEvent(uuid.uuid4(), OrderState.FILLED, 1.0, 100.0),
                now=NOW,
            )
