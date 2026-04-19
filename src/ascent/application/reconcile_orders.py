"""OrderReconciler — startup reconciliation of stale orders against the exchange.

For each non-terminal order whose parent trade is non-terminal, asks the
exchange what happened to it, then feeds a synthetic ``FillEvent`` through
the :class:`FillProcessor`. One code path for live fills and reconciliation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from ascent.application.process_fill import FillProcessor
from ascent.domain import FillEvent, OrderState
from ascent.exchanges.base import OrderStatusResponse
from ascent.ports import (
    ExchangePort,
    OrderRepository,
    TradeRepository,
    UnitOfWorkFactory,
)

logger = logging.getLogger(__name__)


class OrderReconciler:
    def __init__(
        self,
        *,
        order_repo: OrderRepository,
        fill_processor: FillProcessor,
        uow_factory: UnitOfWorkFactory,
        trade_repo: TradeRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._fills = fill_processor
        self._uow_factory = uow_factory
        # Optional: self-heal legacy trades with missing entry_order_id linkage.
        self._trades = trade_repo

    async def reconcile(
        self,
        *,
        exchange: ExchangePort,
        exchange_id: uuid.UUID,
        now: datetime,
    ) -> int:
        async with self._uow_factory() as uow:
            stale = await self._orders.list_for_exchange(
                uow.session, exchange_id, only_non_terminal_trades=True
            )
        if not stale:
            logger.info("Reconciliation: no stale orders on exchange %s", exchange_id)
            return 0

        logger.info("Reconciliation: checking %d stale order(s)", len(stale))
        count = 0
        for order, leg_id, trade_id in stale:
            if self._trades is not None:
                await self._heal_linkage(order=order, leg_id=leg_id, trade_id=trade_id)
            status = await self._lookup(exchange, order)
            event = _to_fill_event(order.id, status)
            if event is None:
                continue
            await self._fills.process(trade_id=trade_id, event=event, now=now)
            count += 1
        logger.info("Reconciliation complete: processed %d", count)
        return count

    async def _heal_linkage(
        self,
        *,
        order,
        leg_id: uuid.UUID,
        trade_id: uuid.UUID,
    ) -> None:
        """Backfill ``TradeLeg.entry_order_id`` / ``exit_order_id`` when the
        original submit path left them NULL. Safe to run repeatedly — only
        writes when the slot is empty.
        """
        async with self._uow_factory() as uow:
            trade = await self._trades.get(uow.session, trade_id)
            if trade is None:
                return
            leg = next((l for l in trade.legs if l.id == leg_id), None)
            if leg is None:
                return
            if leg.entry_order is None:
                await self._trades.set_entry_order(uow.session, leg_id, order.id)
            elif leg.exit_order is None and leg.entry_order.id != order.id:
                await self._trades.set_exit_order(uow.session, leg_id, order.id)

    async def _lookup(self, exchange: ExchangePort, order) -> OrderStatusResponse | None:
        if order.external_order_id:
            return await exchange.get_order_status(order.external_order_id)
        try:
            return await exchange.get_order_by_client_id(str(order.id))
        except NotImplementedError:
            return None


def _to_fill_event(order_id: uuid.UUID, status: OrderStatusResponse | None) -> FillEvent | None:
    if status is None or status.status == "NOT_FOUND":
        return FillEvent(order_id=order_id, state=OrderState.CANCELLED)
    try:
        state = OrderState(status.status)
    except ValueError:
        logger.warning("Reconciliation: unknown exchange status '%s'", status.status)
        return None
    return FillEvent(
        order_id=order_id,
        state=state,
        filled_quantity=status.filled_quantity or 0.0,
        average_fill_price=status.average_fill_price,
        external_order_id=status.exchange_order_id,
        error_message=status.error_message,
    )


_ = datetime  # re-export anchor
