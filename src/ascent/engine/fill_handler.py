"""Fill handler — processes asynchronous order fill updates from exchanges.

Subscribes to all active exchange response channels and persists fill updates
(PARTIALLY_FILLED → FILLED) to the database.  When all legs of a trade are
filled, the trade status is advanced accordingly (OPENING → OPEN, CLOSING →
CLOSED with PnL).

This component bridges the gap between the exchange monitor (which publishes
``order_update`` events via Redis) and the database order/trade records.
"""

from __future__ import annotations

import datetime
import logging
import signal
import threading
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.engine.cache import EngineCache
from ascent.engine.type_cache import TypeCache

logger = logging.getLogger(__name__)


def _process_fill(
    response: dict,
    order_id: str | None,
    trade_id: str | None,
    trade_leg_id: str | None,
    exchange_id: str | None,
    session_factory: sessionmaker,
    type_cache: TypeCache,
) -> None:
    """Persist a single fill update to the database."""
    from ascent.database.models.orders import Order, OrderStatus
    from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

    status = response.get("status")
    if not status or not order_id:
        return

    now = datetime.datetime.now(tz=datetime.UTC)

    with Session(bind=session_factory.kw["bind"]) as db:
        db_order = db.get(Order, uuid.UUID(order_id))
        if db_order is None:
            logger.warning("Fill handler: order %s not found in DB", order_id)
            return

        # Update order fill state
        filled_qty = response.get("filled_quantity", 0.0)
        avg_price = response.get("average_fill_price")
        ext_id = response.get("exchange_order_id")

        if filled_qty is not None:
            db_order.filled_quantity = filled_qty
        if avg_price is not None:
            db_order.average_fill_price = avg_price
        if ext_id and not db_order.external_order_id:
            db_order.external_order_id = ext_id

        # Record order status transition
        if status in ("PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"):
            status_type_id = type_cache.order_status_type_id(status)
            db.add(
                OrderStatus(
                    timestamp=now,
                    order_id=db_order.id,
                    order_status_type_id=status_type_id,
                    error_message=response.get("error_message"),
                )
            )

        db.commit()

        if status == "FILLED":
            logger.info(
                "Order %s FILLED: qty=%.4f @ %s",
                order_id,
                filled_qty or 0,
                avg_price,
            )

            # Update the trade leg entry/exit price
            if trade_leg_id:
                db_leg = db.get(TradeLeg, uuid.UUID(trade_leg_id))
                if db_leg and avg_price is not None:
                    # Determine if this is an entry or exit order
                    if db_leg.entry_order_id == db_order.id:
                        db_leg.entry_price = avg_price
                    elif db_leg.exit_order_id == db_order.id:
                        db_leg.exit_price = avg_price
                    db.commit()

            # Check if all legs of the trade are now filled
            if trade_id:
                _check_trade_complete(
                    db, uuid.UUID(trade_id), now, type_cache
                )

        elif status == "PARTIALLY_FILLED":
            logger.info(
                "Order %s PARTIALLY_FILLED: qty=%.4f / %.4f",
                order_id,
                filled_qty or 0,
                db_order.quantity,
            )


def _check_trade_complete(
    db: Session,
    trade_id: uuid.UUID,
    now: datetime.datetime,
    type_cache: TypeCache,
) -> None:
    """If all legs of a trade are fully filled, advance the trade status."""
    from ascent.database.models.orders import Order
    from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

    trade = db.get(Trade, trade_id)
    if trade is None:
        return

    legs = db.execute(select(TradeLeg).where(TradeLeg.trade_id == trade_id)).scalars().all()
    if not legs:
        return

    current_status_name = type_cache.trade_status_name(trade.current_status_type_id)

    if current_status_name == "OPENING":
        # Check if all entry orders are filled
        all_filled = True
        for leg in legs:
            if leg.entry_order_id is None:
                all_filled = False
                break
            entry_order = db.get(Order, leg.entry_order_id)
            if entry_order is None or entry_order.filled_quantity is None:
                all_filled = False
                break
            if entry_order.filled_quantity < entry_order.quantity:
                all_filled = False
                break

        if all_filled:
            trade.current_status_type_id = type_cache.trade_status_type_id("OPEN")
            db.add(
                TradeStatus(
                    timestamp=now,
                    trade_id=trade_id,
                    trade_status_type_id=type_cache.trade_status_type_id("OPEN"),
                )
            )
            db.commit()
            logger.info("Trade %s → OPEN (%d legs filled)", trade_id, len(legs))

    elif current_status_name == "CLOSING":
        # Check if all exit orders are filled
        all_filled = True
        total_pnl = 0.0
        for leg in legs:
            if leg.exit_order_id is None:
                all_filled = False
                break
            exit_order = db.get(Order, leg.exit_order_id)
            if exit_order is None or exit_order.filled_quantity is None:
                all_filled = False
                break
            if exit_order.filled_quantity < exit_order.quantity:
                all_filled = False
                break

            # Compute PnL for this leg
            entry = leg.entry_price or 0.0
            exit_price = leg.exit_price or exit_order.average_fill_price or 0.0
            if leg.direction == "LONG":
                pnl = (exit_price - entry) * leg.quantity
            else:
                pnl = (entry - exit_price) * leg.quantity
            leg.realized_pnl = round(pnl, 6)
            total_pnl += pnl

        if all_filled:
            trade.current_status_type_id = type_cache.trade_status_type_id("CLOSED")
            trade.exit_at = now
            trade.total_realized_pnl = round(total_pnl, 6)
            db.add(
                TradeStatus(
                    timestamp=now,
                    trade_id=trade_id,
                    trade_status_type_id=type_cache.trade_status_type_id("CLOSED"),
                )
            )
            db.commit()
            logger.info(
                "Trade %s → CLOSED  pnl=%.4f", trade_id, total_pnl
            )


def run_fill_handler(
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
    shutdown_event: threading.Event | None = None,
) -> None:
    """Run the fill handler as a long-running Redis consumer.

    Subscribes to all active exchange response channels and processes
    ``order_update`` events, persisting fill state to the database.
    """
    from ascent.database.models.exchanges import Exchange as ExchangeModel

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)
    type_cache = TypeCache(session_factory)

    # Load all active exchanges and subscribe to their response channels
    with Session(engine) as db:
        exchanges = (
            db.execute(
                select(ExchangeModel).where(ExchangeModel.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        if not exchanges:
            logger.warning("No active exchanges found — fill handler has nothing to do")
            return

        channels = [f"ascent.exchange.{ex.id}.responses" for ex in exchanges]
        exchange_names = {str(ex.id): ex.name for ex in exchanges}

    pubsub = cache.subscribe(channels)

    logger.info(
        "Fill handler started, subscribed to %d exchange(s): %s",
        len(channels),
        ", ".join(exchange_names.values()),
    )

    shutdown = shutdown_event or threading.Event()

    if shutdown_event is None:

        def _signal_handler(signum, _frame):
            logger.info("Received signal %s, shutting down fill handler", signum)
            shutdown.set()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        action = event.get("action")
        if action != "order_update":
            continue

        try:
            _process_fill(
                response=event.get("response", {}),
                order_id=event.get("order_id"),
                trade_id=event.get("trade_id"),
                trade_leg_id=event.get("trade_leg_id"),
                exchange_id=event.get("exchange_id"),
                session_factory=session_factory,
                type_cache=type_cache,
            )
            # Notify the UI via a dedicated channel
            trade_id = event.get("trade_id")
            if trade_id:
                cache.publish(
                    "ascent.trades.updates",
                    {"event": "trade_updated", "trade_id": trade_id},
                )
        except Exception:
            logger.exception(
                "Error processing fill update for order %s", event.get("order_id")
            )

    pubsub.close()
    logger.info("Fill handler shut down cleanly")
