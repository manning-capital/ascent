"""Fill-handling use case — single entry point for both live fills and reconciliation.

Given a ``FillEvent`` on one of a trade's orders, this:
1. Persists the order-side changes (status, fill qty, price, external id).
2. Asks :func:`ascent.domain.apply_fill` what the trade should transition to.
3. Persists the leg and trade updates.
4. Publishes a UI notification.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from ascent.domain import FillEvent, apply_fill
from ascent.ports import EventBus, OrderRepository, TradeRepository

logger = logging.getLogger(__name__)

UI_CHANNEL = "ascent.trades.updates"


class FillProcessor:
    def __init__(
        self,
        *,
        trade_repo: TradeRepository,
        order_repo: OrderRepository,
        event_bus: EventBus,
    ) -> None:
        self._trades = trade_repo
        self._orders = order_repo
        self._bus = event_bus

    async def process(
        self,
        *,
        trade_id: uuid.UUID,
        event: FillEvent,
        now: datetime,
    ) -> None:
        trade = await self._trades.get(trade_id)
        if trade is None:
            logger.warning("FillProcessor: trade %s not found; dropping event", trade_id)
            return

        await self._apply_order_side_updates(event=event, now=now)

        try:
            transition = apply_fill(trade, event, now=now)
        except ValueError as exc:
            # Legacy trades (written before TradeRouter.submit linked
            # TradeLeg.entry_order_id) arrive with ``leg.entry_order = None``
            # even though ``Order.trade_leg_id`` points the other way. Log
            # and drop rather than tearing down the whole service task.
            logger.warning(
                "FillProcessor: cannot locate order on trade — skipping event. %s",
                exc,
            )
            return

        for leg_update in transition.leg_updates:
            await self._trades.set_leg_prices(
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
                trade_id,
                new_state=transition.new_state,
                at=now,
                exit_at=transition.exit_at,
                total_realized_pnl=transition.total_realized_pnl,
            )

        await self._bus.publish(UI_CHANNEL, {"event": "trade_updated", "trade_id": str(trade_id)})

    async def _apply_order_side_updates(self, *, event: FillEvent, now: datetime) -> None:
        await self._orders.record_status(
            event.order_id,
            new_state=event.state,
            at=now,
            error_message=event.error_message,
        )
        if event.filled_quantity or event.average_fill_price is not None:
            await self._orders.set_fill(
                event.order_id,
                filled_quantity=event.filled_quantity,
                average_fill_price=event.average_fill_price,
            )
        if event.external_order_id:
            await self._orders.set_external_id(event.order_id, event.external_order_id)
