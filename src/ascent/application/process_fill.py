"""Fill-handling use case — single entry point for both live fills and reconciliation.

Given a ``FillEvent`` on one of a trade's orders, this:
1. Persists the order-side changes (status, fill qty, price, external id).
2. Asks :func:`ascent.domain.apply_fill` what the trade should transition to.
3. Persists the leg and trade updates.
4. Records a ``Transaction`` row and adjusts the strategy's
   ``StrategyAssetHolding`` (the double-entry counterparts) when a fill
   actually moves units.
5. Publishes a UI notification post-commit.

All DB mutations run inside one :class:`UnitOfWork` so a partial failure
rolls back cleanly — we never leave an order row updated without the
corresponding trade-state row.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime
from decimal import Decimal

from ascent.domain import FillEvent, OrderState, PositionType, Trade, apply_fill
from ascent.ports import (
    EventBus,
    HoldingsRepository,
    InstrumentRepository,
    NewTransactionSpec,
    OrderRepository,
    TradeRepository,
    TransactionRepository,
    UnitOfWorkFactory,
)

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


def _locate_leg_for_event(trade: Trade, order_id: uuid.UUID):
    """Return ``(leg, is_entry)`` for the leg this order belongs to.

    Returns ``(None, False)`` if the order is not on any leg.
    """
    for leg in trade.legs:
        if leg.entry_order and leg.entry_order.id == order_id:
            return leg, True
        if leg.exit_order and leg.exit_order.id == order_id:
            return leg, False
    return None, False


def _exchange_id_for_event(trade: Trade, order_id: uuid.UUID):
    """Return the exchange_id of the leg the order belongs to."""
    leg, _ = _locate_leg_for_event(trade, order_id)
    return None if leg is None else leg.exchange_id


class FillProcessor:
    def __init__(
        self,
        *,
        trade_repo: TradeRepository,
        order_repo: OrderRepository,
        event_bus: EventBus,
        uow_factory: UnitOfWorkFactory,
        holdings_repo: HoldingsRepository | None = None,
        transactions_repo: TransactionRepository | None = None,
        instrument_repo: InstrumentRepository | None = None,
    ) -> None:
        self._trades = trade_repo
        self._orders = order_repo
        self._bus = event_bus
        self._uow_factory = uow_factory
        # Holdings + transactions are optional — when any is missing the
        # double-entry side is silently skipped. Production callers wire
        # all three; lighter-weight tests can opt out.
        self._holdings = holdings_repo
        self._transactions = transactions_repo
        self._instruments = instrument_repo

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

            await self._write_double_entry(uow.session, trade=trade, event=event, now=now)

        await self._bus.publish(UI_CHANNEL, {"event": "trade_updated", "trade_id": str(trade_id)})

    async def _write_double_entry(
        self, session, *, trade: Trade, event: FillEvent, now: datetime
    ) -> None:
        """Record a Transaction row + adjust StrategyAssetHolding for this fill.

        Skipped when:
        - any of holdings_repo / transactions_repo / instrument_repo is unwired
          (lighter-weight tests run that way),
        - the fill carried no actual quantity movement (status-only event),
        - the leg can't be located on the trade,
        - the instrument's asset metadata isn't available.
        """
        if self._holdings is None or self._transactions is None or self._instruments is None:
            return
        if not event.filled_quantity:
            return

        leg, is_entry = _locate_leg_for_event(trade, event.order_id)
        if leg is None:
            return

        assets = await self._instruments.get_asset_ids(session, [leg.instrument_id])
        info = assets.get(leg.instrument_id)
        if info is None:
            logger.warning(
                "FillProcessor: no asset metadata for instrument %s; "
                "skipping holdings/transaction write",
                leg.instrument_id,
            )
            return

        quantity = Decimal(str(event.filled_quantity))
        # On an entry fill the strategy gains exposure (delta = +qty); on an
        # exit fill it bleeds back out (delta = -qty). The sign is on
        # quantity_delta, never on position_type — we always update the row
        # the original leg booked into.
        delta = quantity if is_entry else -quantity
        position_type = leg.direction
        # Side: BUY when entering LONG or exiting SHORT; SELL otherwise.
        side = (
            "BUY"
            if (is_entry and position_type == PositionType.LONG)
            or (not is_entry and position_type == PositionType.SHORT)
            else "SELL"
        )
        # from_asset / to_asset ordering on Transaction follows the trade
        # action: a BUY moves quote → base, a SELL moves base → quote.
        if side == "BUY":
            tx_from_asset, tx_to_asset = info.to_asset_id, info.from_asset_id
        else:
            tx_from_asset, tx_to_asset = info.from_asset_id, info.to_asset_id

        await self._transactions.record(
            session,
            NewTransactionSpec(
                timestamp=now,
                transaction_type=side,
                from_asset_id=tx_from_asset,
                to_asset_id=tx_to_asset,
                quantity=event.filled_quantity,
                price=event.average_fill_price or 0.0,
                strategy_id=trade.strategy_id,
                trade_leg_id=leg.id,
            ),
        )

        # The order/leg's exchange is the one the position settles on; we
        # need it to key the holding row. Pull from the entry/exit Order
        # since neither the leg domain type nor the FillEvent carries the
        # exchange id directly.
        exchange_id = _exchange_id_for_event(trade, event.order_id)
        if exchange_id is None:
            logger.warning(
                "FillProcessor: cannot resolve exchange for order %s; skipping holdings update",
                event.order_id,
            )
            return

        await self._holdings.apply_delta(
            session,
            strategy_id=trade.strategy_id,
            exchange_id=exchange_id,
            asset_id=info.from_asset_id,
            position_type=position_type,
            quantity_delta=delta,
            at=now,
        )

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
