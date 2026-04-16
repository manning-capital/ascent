"""Pure trade state transitions — no I/O, no DB, no framework calls.

The single public entry point is :func:`apply_fill`, which computes the
deterministic result of applying a fill event to a trade. The caller
(a use case) decides what to persist.

Call :func:`opening_from_orders` when a trade has just had all its entry
orders submitted — it confirms OPENING is the right starting state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from ascent.domain.trade import (
    Direction,
    FillEvent,
    Order,
    OrderState,
    Trade,
    TradeState,
)


@dataclass(frozen=True)
class OrderUpdate:
    order_id: uuid.UUID
    new_state: OrderState
    filled_quantity: float
    average_fill_price: float | None
    external_order_id: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class LegUpdate:
    leg_id: uuid.UUID
    entry_price: float | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None


@dataclass(frozen=True)
class TradeTransition:
    new_state: TradeState
    order_updates: tuple[OrderUpdate, ...] = ()
    leg_updates: tuple[LegUpdate, ...] = ()
    total_realized_pnl: float | None = None
    exit_at: datetime | None = None


def apply_fill(trade: Trade, event: FillEvent, *, now: datetime) -> TradeTransition:
    """Compute the deterministic result of applying ``event`` to ``trade``.

    The caller applies the returned updates to persistent storage. The state
    machine only makes decisions; it does not perform I/O.

    Raises:
        ValueError: if ``event.order_id`` does not match any order on the trade.
    """
    leg_idx, is_entry = _locate_order(trade, event.order_id)

    order_update = OrderUpdate(
        order_id=event.order_id,
        new_state=event.state,
        filled_quantity=event.filled_quantity,
        average_fill_price=event.average_fill_price,
        external_order_id=event.external_order_id,
        error_message=event.error_message,
    )

    leg_updates: list[LegUpdate] = []
    if event.state == OrderState.FILLED and event.average_fill_price is not None:
        leg = trade.legs[leg_idx]
        if is_entry:
            leg_updates.append(LegUpdate(leg_id=leg.id, entry_price=event.average_fill_price))
        else:
            pnl = _compute_leg_pnl(
                direction=leg.direction,
                entry_price=leg.entry_price or 0.0,
                exit_price=event.average_fill_price,
                quantity=leg.quantity,
            )
            leg_updates.append(
                LegUpdate(
                    leg_id=leg.id,
                    exit_price=event.average_fill_price,
                    realized_pnl=round(pnl, 6),
                )
            )

    projected = _project_orders(trade, order_update)
    new_state, total_pnl, exit_at = _compute_trade_state(
        trade=trade,
        projected_orders=projected,
        leg_updates=tuple(leg_updates),
        now=now,
    )

    return TradeTransition(
        new_state=new_state,
        order_updates=(order_update,),
        leg_updates=tuple(leg_updates),
        total_realized_pnl=total_pnl,
        exit_at=exit_at,
    )


def opening_from_orders(trade: Trade) -> TradeState:
    """Compute the state a trade should transition to after entry orders are submitted.

    Called right after ``TradeRouter.submit`` creates the entry orders. The
    trade is PENDING; this returns OPENING if all entry orders exist and are
    active, otherwise ERROR.
    """
    if not trade.legs:
        return TradeState.ERROR
    for leg in trade.legs:
        if leg.entry_order is None or not leg.entry_order.state.is_active:
            return TradeState.ERROR
    return TradeState.OPENING


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _locate_order(trade: Trade, order_id: uuid.UUID) -> tuple[int, bool]:
    for idx, leg in enumerate(trade.legs):
        if leg.entry_order and leg.entry_order.id == order_id:
            return idx, True
        if leg.exit_order and leg.exit_order.id == order_id:
            return idx, False
    raise ValueError(f"Order {order_id} is not on trade {trade.id}")


def _project_orders(trade: Trade, update: OrderUpdate) -> dict[uuid.UUID, OrderState]:
    """Apply the incoming update onto the trade's current orders to produce
    the post-update state map used by :func:`_compute_trade_state`.
    """
    projected: dict[uuid.UUID, OrderState] = {}
    for leg in trade.legs:
        if leg.entry_order:
            projected[leg.entry_order.id] = leg.entry_order.state
        if leg.exit_order:
            projected[leg.exit_order.id] = leg.exit_order.state
    projected[update.order_id] = update.new_state
    return projected


def _compute_trade_state(
    *,
    trade: Trade,
    projected_orders: dict[uuid.UUID, OrderState],
    leg_updates: tuple[LegUpdate, ...],
    now: datetime,
) -> tuple[TradeState, float | None, datetime | None]:
    current = trade.state

    if current == TradeState.OPENING:
        return _resolve_opening(trade, projected_orders)

    if current == TradeState.CLOSING:
        return _resolve_closing(trade, projected_orders, leg_updates, now)

    if current == TradeState.ERROR:
        return _resolve_error(trade, projected_orders)

    # PENDING / OPEN / CANCELLED / CLOSED — fills don't move these.
    return current, trade.total_realized_pnl, trade.exit_at


def _resolve_opening(
    trade: Trade,
    projected: dict[uuid.UUID, OrderState],
) -> tuple[TradeState, float | None, datetime | None]:
    all_filled = True
    any_active = False
    for leg in trade.legs:
        eo = leg.entry_order
        if eo is None:
            all_filled = False
            continue
        state = projected.get(eo.id, eo.state)
        if state == OrderState.FILLED:
            continue
        if state.is_active:
            all_filled = False
            any_active = True
        else:
            all_filled = False

    if all_filled:
        return TradeState.OPEN, trade.total_realized_pnl, trade.exit_at
    if not any_active:
        return TradeState.CANCELLED, trade.total_realized_pnl, trade.exit_at
    return TradeState.OPENING, trade.total_realized_pnl, trade.exit_at


def _resolve_closing(
    trade: Trade,
    projected: dict[uuid.UUID, OrderState],
    leg_updates: tuple[LegUpdate, ...],
    now: datetime,
) -> tuple[TradeState, float | None, datetime | None]:
    all_filled = True
    any_active = False
    for leg in trade.legs:
        xo = leg.exit_order
        if xo is None:
            all_filled = False
            continue
        state = projected.get(xo.id, xo.state)
        if state == OrderState.FILLED:
            continue
        if state.is_active:
            all_filled = False
            any_active = True
        else:
            all_filled = False

    if all_filled:
        total = _sum_pnl(trade, leg_updates)
        return TradeState.CLOSED, total, now
    if not any_active:
        # Exit orders failed but entry position still held → reopen.
        return TradeState.OPEN, trade.total_realized_pnl, trade.exit_at
    return TradeState.CLOSING, trade.total_realized_pnl, trade.exit_at


def _resolve_error(
    trade: Trade,
    projected: dict[uuid.UUID, OrderState],
) -> tuple[TradeState, float | None, datetime | None]:
    any_active = False
    any_filled = False
    for leg in trade.legs:
        for order in (leg.entry_order, leg.exit_order):
            if order is None:
                continue
            state = projected.get(order.id, order.state)
            if state.is_active:
                any_active = True
            if state == OrderState.FILLED:
                any_filled = True

    if any_active:
        return TradeState.ERROR, trade.total_realized_pnl, trade.exit_at

    if any_filled and _all_entries_filled(trade, projected):
        return TradeState.OPEN, trade.total_realized_pnl, trade.exit_at

    if not any_filled:
        return TradeState.CANCELLED, trade.total_realized_pnl, trade.exit_at

    # Partial fills — leave ERROR for manual review.
    return TradeState.ERROR, trade.total_realized_pnl, trade.exit_at


def _all_entries_filled(trade: Trade, projected: dict[uuid.UUID, OrderState]) -> bool:
    for leg in trade.legs:
        if leg.entry_order is None:
            return False
        if projected.get(leg.entry_order.id, leg.entry_order.state) != OrderState.FILLED:
            return False
    return True


def _sum_pnl(trade: Trade, leg_updates: tuple[LegUpdate, ...]) -> float:
    pnl_by_leg: dict[uuid.UUID, float] = {leg.id: leg.realized_pnl or 0.0 for leg in trade.legs}
    for update in leg_updates:
        if update.realized_pnl is not None:
            pnl_by_leg[update.leg_id] = update.realized_pnl
    return round(sum(pnl_by_leg.values()), 6)


def _compute_leg_pnl(
    *, direction: Direction, entry_price: float, exit_price: float, quantity: float
) -> float:
    if direction == Direction.LONG:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity


__all__ = [
    "LegUpdate",
    "OrderUpdate",
    "TradeTransition",
    "apply_fill",
    "opening_from_orders",
]


# For type hint re-exports only.
_ = Order
