"""Fill-handling use case — single entry point for both live fills and reconciliation.

Given a ``FillEvent`` on one of a trade's orders, this:
1. Persists the order-side changes (status, fill qty, price, external id).
2. Asks :func:`ascent.domain.apply_fill` what the trade should transition to.
3. Persists the leg and trade updates.
4. Publishes a UI notification post-commit.

All DB mutations run inside one :class:`UnitOfWork` so a partial failure
rolls back cleanly — we never leave an order row updated without the
corresponding trade-state row.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime

from ascent.domain import FillEvent, OrderState, Trade, apply_fill
from ascent.ports import EventBus, OrderRepository, TradeRepository, UnitOfWorkFactory

logger = logging.getLogger(__name__)

UI_CHANNEL = "ascent.trades.updates"

# Absolute float tolerance for "filled_quantity effectively covers the order".
# Tuned for the observed drift (~1e-17 on 0.01-sized orders, well inside this
# bound). If a real exchange ever needs a looser tolerance, make this a
# per-exchange configuration instead of a module constant.
_FILL_EPSILON = 1e-9


def _canonicalize_fill(event: FillEvent, trade: Trade) -> FillEvent:
    """Promote a near-complete ``PARTIALLY_FILLED`` event to ``FILLED``.

    Rule: trust the numbers over the label. If the exchange reports
    ``PARTIALLY_FILLED`` but ``filled_quantity`` already covers the ordered
    quantity (within :data:`_FILL_EPSILON`), the order IS filled — promote.
    Also snaps ``filled_quantity`` to the exact ordered amount so downstream
    PnL calculations don't carry the drifted value.

    Terminal non-filled states (CANCELLED, REJECTED) are authoritative and
    never promoted, even if they arrive with a near-full filled quantity.
    """
    if event.state != OrderState.PARTIALLY_FILLED:
        return event
    ordered_qty = _find_ordered_quantity(trade, event.order_id)
    if ordered_qty is None:
        return event
    if event.filled_quantity + _FILL_EPSILON < ordered_qty:
        return event
    return dataclasses.replace(
        event,
        state=OrderState.FILLED,
        filled_quantity=ordered_qty,
    )


def _find_ordered_quantity(trade: Trade, order_id: uuid.UUID) -> float | None:
    for leg in trade.legs:
        if leg.entry_order and leg.entry_order.id == order_id:
            return leg.entry_order.quantity
        if leg.exit_order and leg.exit_order.id == order_id:
            return leg.exit_order.quantity
    return None


class FillProcessor:
    def __init__(
        self,
        *,
        trade_repo: TradeRepository,
        order_repo: OrderRepository,
        event_bus: EventBus,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._trades = trade_repo
        self._orders = order_repo
        self._bus = event_bus
        self._uow_factory = uow_factory

    async def process(
        self,
        *,
        trade_id: uuid.UUID,
        event: FillEvent,
        now: datetime,
    ) -> None:
        async with self._uow_factory() as uow:
            trade = await self._trades.get(uow.session, trade_id)
            if trade is None:
                logger.warning("FillProcessor: trade %s not found; dropping event", trade_id)
                return

            # Trust the numbers over the label: a PARTIALLY_FILLED report
            # whose quantity already covers the order is FILLED, regardless
            # of the exchange's label. Prevents trades sticking in OPENING/
            # CLOSING due to float drift in fill-size accumulation.
            event = _canonicalize_fill(event, trade)

            await self._apply_order_side_updates(uow.session, event=event, now=now)

            try:
                transition = apply_fill(trade, event, now=now)
            except ValueError as exc:
                # Legacy trades (written before TradeRouter linked
                # TradeLeg.entry_order_id) arrive with ``leg.entry_order = None``
                # even though ``Order.trade_leg_id`` points the other way.
                logger.warning(
                    "FillProcessor: cannot locate order on trade — skipping event. %s",
                    exc,
                )
                return

            for leg_update in transition.leg_updates:
                await self._trades.set_leg_prices(
                    uow.session,
                    leg_update.leg_id,
                    entry_price=leg_update.entry_price,
                    exit_price=leg_update.exit_price,
                    realized_pnl=leg_update.realized_pnl,
                )

            if (
                transition.new_state != trade.state
                or transition.total_realized_pnl is not None
                or transition.exit_at is not None
            ):
                await self._trades.set_state(
                    uow.session,
                    trade_id,
                    new_state=transition.new_state,
                    at=now,
                    exit_at=transition.exit_at,
                    total_realized_pnl=transition.total_realized_pnl,
                )

        await self._bus.publish(UI_CHANNEL, {"event": "trade_updated", "trade_id": str(trade_id)})

    async def _apply_order_side_updates(self, session, *, event: FillEvent, now: datetime) -> None:
        await self._orders.record_status(
            session,
            event.order_id,
            new_state=event.state,
            at=now,
            error_message=event.error_message,
        )
        if event.filled_quantity or event.average_fill_price is not None:
            await self._orders.set_fill(
                session,
                event.order_id,
                filled_quantity=event.filled_quantity,
                average_fill_price=event.average_fill_price,
            )
        if event.external_order_id:
            await self._orders.set_external_id(session, event.order_id, event.external_order_id)
