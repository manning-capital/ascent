"""Exchange runner — dispatches orders and monitors fill status via Redis.

Runs two concurrent loops in the same thread group:

1. **Dispatch loop** (main thread) — subscribes to Redis pub/sub and routes
   incoming ``submit_order`` / ``cancel_order`` / ``get_balances`` actions to
   the exchange implementation.
2. **Monitor loop** (background thread) — tracks open orders and publishes
   status changes back via Redis.  Automatically selects between:
   - *polling* — periodically calls ``exchange.get_open_orders()``
   - *streaming* — consumes ``exchange.connect_order_stream()``
   depending on which method the exchange class overrides.
"""

from __future__ import annotations

import datetime
import logging
import signal
import threading
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.engine.cache import EngineCache
from ascent.engine.type_cache import TypeCache

if TYPE_CHECKING:
    from ascent.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)

# Terminal order states — no further updates expected.
_TERMINAL = frozenset({"FILLED", "CANCELLED", "REJECTED", "NOT_FOUND"})

# Terminal trade states — reconciliation skips these.
_TRADE_TERMINAL = frozenset({"CLOSED", "CANCELLED"})


# ------------------------------------------------------------------
# Order tracker — shared between dispatch and monitor threads
# ------------------------------------------------------------------


class _OrderTracker:
    """Thread-safe registry of open orders and their correlation IDs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders: dict[str, dict[str, Any]] = {}

    def track(
        self,
        exchange_order_id: str,
        *,
        order_id: str | None = None,
        trade_id: str | None = None,
        trade_leg_id: str | None = None,
    ) -> None:
        with self._lock:
            self._orders[exchange_order_id] = {
                "order_id": order_id,
                "trade_id": trade_id,
                "trade_leg_id": trade_leg_id,
                "last_status": None,
                "last_filled_qty": 0.0,
            }

    def resolve(self, exchange_order_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._orders.get(exchange_order_id)

    def close(self, exchange_order_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._orders.pop(exchange_order_id, None)

    def has_open(self) -> bool:
        with self._lock:
            return bool(self._orders)


# ------------------------------------------------------------------
# Monitor loops
# ------------------------------------------------------------------


def _publish_update(
    cache: EngineCache,
    channel: str,
    exchange_id: str,
    meta: dict[str, Any],
    response: dict[str, Any],
) -> None:
    cache.publish(
        f"{channel}.responses",
        {
            "action": "order_update",
            "exchange_id": exchange_id,
            "order_id": meta.get("order_id"),
            "trade_id": meta.get("trade_id"),
            "trade_leg_id": meta.get("trade_leg_id"),
            "response": response,
        },
    )


def _poll_monitor(
    exchange: BaseExchange,
    cache: EngineCache,
    channel: str,
    exchange_id: str,
    tracker: _OrderTracker,
    shutdown: threading.Event,
) -> None:
    """Periodically call ``get_open_orders`` and publish state changes."""
    logger.info("Poll monitor started (interval=%.1fs)", exchange.poll_interval)

    while not shutdown.is_set():
        if not tracker.has_open():
            shutdown.wait(exchange.poll_interval)
            continue

        try:
            statuses = exchange.get_open_orders()
        except Exception:
            logger.exception("Error polling open orders")
            shutdown.wait(exchange.poll_interval)
            continue

        for status in statuses:
            meta = tracker.resolve(status.exchange_order_id)
            if meta is None:
                continue

            changed = (
                status.status != meta["last_status"]
                or status.filled_quantity != meta["last_filled_qty"]
            )
            if not changed:
                continue

            meta["last_status"] = status.status
            meta["last_filled_qty"] = status.filled_quantity

            _publish_update(cache, channel, exchange_id, meta, status.model_dump())

            logger.info(
                "Order %s → %s (filled=%.4f)",
                status.exchange_order_id,
                status.status,
                status.filled_quantity,
            )

            if status.status in _TERMINAL:
                tracker.close(status.exchange_order_id)

        shutdown.wait(exchange.poll_interval)

    logger.info("Poll monitor stopped")


def _stream_monitor(
    exchange: BaseExchange,
    cache: EngineCache,
    channel: str,
    exchange_id: str,
    tracker: _OrderTracker,
    shutdown: threading.Event,
) -> None:
    """Consume ``connect_order_stream`` and publish each event."""
    logger.info("Stream monitor started")

    try:
        for event in exchange.connect_order_stream(shutdown):
            if shutdown.is_set():
                break

            meta = tracker.resolve(event.exchange_order_id)
            if meta is None:
                continue

            _publish_update(
                cache,
                channel,
                exchange_id,
                meta,
                {
                    "exchange_order_id": event.exchange_order_id,
                    "status": event.status,
                    "filled_quantity": event.filled_quantity,
                    "average_fill_price": event.average_fill_price,
                },
            )

            logger.info(
                "Order %s → %s (filled=%.4f)",
                event.exchange_order_id,
                event.status,
                event.filled_quantity,
            )

            if event.status in _TERMINAL:
                tracker.close(event.exchange_order_id)
    except Exception:
        logger.exception("Stream monitor error")

    logger.info("Stream monitor stopped")


# ------------------------------------------------------------------
# Reconciliation — runs on startup
# ------------------------------------------------------------------


def _reconcile(
    exchange: BaseExchange,
    exchange_id: uuid.UUID,
    tracker: _OrderTracker,
    session_factory: sessionmaker,
    type_cache: TypeCache,
) -> None:
    """Check stale DB orders against the exchange and resolve discrepancies.

    Called once at startup before the dispatch/monitor loops begin.

    For each non-terminal order on this exchange:
    - If the exchange says FILLED → update the DB order and advance the trade.
    - If the exchange says still open → re-register in the tracker so the
      monitor picks it up.
    - If the exchange has no record of it → cancel the order.

    After processing all orders, check whether any trades can be advanced
    (OPENING → OPEN, CLOSING → CLOSED) or should be cancelled.
    """
    from ascent.database.models.orders import Order, OrderStatus
    from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

    terminal_trade_ids = {
        type_cache.trade_status_type_id(n)
        for n in _TRADE_TERMINAL
        if n in type_cache._trade_status_types
    }

    with Session(bind=session_factory.kw["bind"]) as db:
        # Find orders on this exchange whose parent trade is non-terminal
        orders = (
            db.execute(
                select(Order)
                .where(Order.exchange_id == exchange_id)
                .where(Order.trade_leg_id.isnot(None))
            )
            .scalars()
            .all()
        )

        # Filter to orders whose trades are non-terminal
        stale: list[tuple[Order, TradeLeg, Trade]] = []
        for order in orders:
            leg = db.get(TradeLeg, order.trade_leg_id)
            if leg is None:
                continue
            trade = db.get(Trade, leg.trade_id)
            if trade is None or trade.current_status_type_id in terminal_trade_ids:
                continue
            stale.append((order, leg, trade))

        if not stale:
            logger.info("Reconciliation: no stale orders")
            return

        logger.info("Reconciliation: checking %d stale order(s)", len(stale))
        now = datetime.datetime.now(tz=datetime.UTC)

        for order, leg, trade in stale:
            exchange_status = None

            # Try to look up the order on the exchange
            if order.external_order_id:
                exchange_status = exchange.get_order_status(order.external_order_id)
            else:
                try:
                    exchange_status = exchange.get_order_by_client_id(str(order.id))
                except NotImplementedError:
                    pass

            if exchange_status is None or exchange_status.status == "NOT_FOUND":
                # Exchange has no record → cancel the order
                if order.filled_quantity is None or order.filled_quantity == 0:
                    db.add(
                        OrderStatus(
                            timestamp=now,
                            order_id=order.id,
                            order_status_type_id=type_cache.order_status_type_id("CANCELLED"),
                        )
                    )
                    logger.info("Reconciliation: order %s not found on exchange → CANCELLED", order.id)
                continue

            # Save exchange_order_id if we didn't have it
            if exchange_status.exchange_order_id and not order.external_order_id:
                order.external_order_id = exchange_status.exchange_order_id

            if exchange_status.status == "FILLED":
                order.filled_quantity = exchange_status.filled_quantity
                order.average_fill_price = exchange_status.average_fill_price
                db.add(
                    OrderStatus(
                        timestamp=now,
                        order_id=order.id,
                        order_status_type_id=type_cache.order_status_type_id("FILLED"),
                    )
                )
                # Update leg price
                if exchange_status.average_fill_price is not None:
                    if leg.entry_order_id == order.id:
                        leg.entry_price = exchange_status.average_fill_price
                    elif leg.exit_order_id == order.id:
                        leg.exit_price = exchange_status.average_fill_price
                logger.info("Reconciliation: order %s → FILLED (qty=%.4f)", order.id, exchange_status.filled_quantity or 0)

            elif exchange_status.status in ("SUBMITTED", "PARTIALLY_FILLED"):
                # Still open → re-register so monitor picks it up
                eid = exchange_status.exchange_order_id or order.external_order_id
                if eid:
                    tracker.track(
                        eid,
                        order_id=str(order.id),
                        trade_id=str(trade.id),
                        trade_leg_id=str(leg.id),
                    )
                    logger.info("Reconciliation: order %s still open → re-registered", order.id)

            elif exchange_status.status == "CANCELLED":
                db.add(
                    OrderStatus(
                        timestamp=now,
                        order_id=order.id,
                        order_status_type_id=type_cache.order_status_type_id("CANCELLED"),
                    )
                )
                logger.info("Reconciliation: order %s → CANCELLED (by exchange)", order.id)

        db.commit()

        # Now check each affected trade and advance/cancel as needed
        seen_trades: set[uuid.UUID] = set()
        for order, leg, trade in stale:
            if trade.id in seen_trades:
                continue
            seen_trades.add(trade.id)
            _reconcile_trade(db, trade, type_cache, now)

        db.commit()

    logger.info("Reconciliation complete")


def _reconcile_trade(
    db: Session,
    trade: Any,
    type_cache: TypeCache,
    now: datetime.datetime,
) -> None:
    """Advance or cancel a single trade based on its current order states."""
    from ascent.database.models.orders import Order, OrderStatus
    from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

    trade = db.get(Trade, trade.id)
    if trade is None:
        return

    status_name = type_cache.trade_status_name(trade.current_status_type_id)
    legs = db.execute(select(TradeLeg).where(TradeLeg.trade_id == trade.id)).scalars().all()
    if not legs:
        return

    if status_name == "OPENING":
        _reconcile_opening(db, trade, legs, type_cache, now)
    elif status_name == "CLOSING":
        _reconcile_closing(db, trade, legs, type_cache, now)
    elif status_name == "ERROR":
        _reconcile_error(db, trade, legs, type_cache, now)


def _get_latest_order_status_name(
    db: Session, order_id: uuid.UUID, type_cache: TypeCache
) -> str | None:
    """Get the latest OrderStatus name for an order."""
    from ascent.database.models.orders import OrderStatus

    latest = (
        db.execute(
            select(OrderStatus)
            .where(OrderStatus.order_id == order_id)
            .order_by(OrderStatus.timestamp.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if latest is None:
        return None
    for name, uid in type_cache._order_status_types.items():
        if uid == latest.order_status_type_id:
            return name
    return None


def _reconcile_opening(db, trade, legs, type_cache, now):
    """OPENING trade: check if entry orders resolved."""
    from ascent.database.models.orders import Order
    from ascent.database.models.trades import TradeStatus

    all_filled = True
    any_active = False

    for leg in legs:
        if leg.entry_order_id is None:
            all_filled = False
            continue
        order = db.get(Order, leg.entry_order_id)
        if order is None:
            all_filled = False
            continue
        status = _get_latest_order_status_name(db, order.id, type_cache)
        if status == "FILLED":
            continue
        elif status in ("SUBMITTED", "PARTIALLY_FILLED"):
            all_filled = False
            any_active = True
        else:
            all_filled = False

    if all_filled:
        trade.current_status_type_id = type_cache.trade_status_type_id("OPEN")
        db.add(TradeStatus(
            timestamp=now, trade_id=trade.id,
            trade_status_type_id=type_cache.trade_status_type_id("OPEN"),
        ))
        logger.info("Reconciliation: trade %s OPENING → OPEN", trade.id)
    elif not any_active:
        # All orders resolved but not all filled → cancel
        trade.current_status_type_id = type_cache.trade_status_type_id("CANCELLED")
        db.add(TradeStatus(
            timestamp=now, trade_id=trade.id,
            trade_status_type_id=type_cache.trade_status_type_id("CANCELLED"),
        ))
        logger.info("Reconciliation: trade %s OPENING → CANCELLED (no active orders)", trade.id)


def _reconcile_closing(db, trade, legs, type_cache, now):
    """CLOSING trade: check if exit orders resolved."""
    from ascent.database.models.orders import Order
    from ascent.database.models.trades import TradeStatus

    all_filled = True
    any_active = False
    total_pnl = 0.0

    for leg in legs:
        if leg.exit_order_id is None:
            all_filled = False
            continue
        order = db.get(Order, leg.exit_order_id)
        if order is None:
            all_filled = False
            continue
        status = _get_latest_order_status_name(db, order.id, type_cache)
        if status == "FILLED":
            entry = leg.entry_price or 0.0
            exit_price = leg.exit_price or order.average_fill_price or 0.0
            pnl = ((exit_price - entry) if leg.direction == "LONG" else (entry - exit_price)) * leg.quantity
            leg.realized_pnl = round(pnl, 6)
            total_pnl += pnl
        elif status in ("SUBMITTED", "PARTIALLY_FILLED"):
            all_filled = False
            any_active = True
        else:
            all_filled = False

    if all_filled:
        trade.current_status_type_id = type_cache.trade_status_type_id("CLOSED")
        trade.exit_at = now
        trade.total_realized_pnl = round(total_pnl, 6)
        db.add(TradeStatus(
            timestamp=now, trade_id=trade.id,
            trade_status_type_id=type_cache.trade_status_type_id("CLOSED"),
        ))
        logger.info("Reconciliation: trade %s CLOSING → CLOSED (pnl=%.4f)", trade.id, total_pnl)
    elif not any_active:
        # Exit orders failed but position still exists → reopen
        trade.current_status_type_id = type_cache.trade_status_type_id("OPEN")
        db.add(TradeStatus(
            timestamp=now, trade_id=trade.id,
            trade_status_type_id=type_cache.trade_status_type_id("OPEN"),
        ))
        logger.info("Reconciliation: trade %s CLOSING → OPEN (exit orders lost, position still held)", trade.id)


def _reconcile_error(db, trade, legs, type_cache, now):
    """ERROR trade: check if any orders actually went through."""
    from ascent.database.models.orders import Order
    from ascent.database.models.trades import TradeStatus

    any_filled = False
    any_active = False

    for leg in legs:
        for order_id in (leg.entry_order_id, leg.exit_order_id):
            if order_id is None:
                continue
            status = _get_latest_order_status_name(db, order_id, type_cache)
            if status == "FILLED":
                any_filled = True
            elif status in ("SUBMITTED", "PARTIALLY_FILLED"):
                any_active = True

    if any_active:
        # Orders still in-flight — leave as ERROR for next reconciliation
        return

    if any_filled:
        # Some orders filled — check if all entry orders filled
        all_entry_filled = all(
            _get_latest_order_status_name(db, leg.entry_order_id, type_cache) == "FILLED"
            for leg in legs
            if leg.entry_order_id
        )
        if all_entry_filled:
            trade.current_status_type_id = type_cache.trade_status_type_id("OPEN")
            db.add(TradeStatus(
                timestamp=now, trade_id=trade.id,
                trade_status_type_id=type_cache.trade_status_type_id("OPEN"),
            ))
            logger.info("Reconciliation: trade %s ERROR → OPEN (entry orders were filled)", trade.id)
        # else: partial fills — leave as ERROR for manual review
    else:
        # Nothing filled, nothing active → safe to cancel
        trade.current_status_type_id = type_cache.trade_status_type_id("CANCELLED")
        db.add(TradeStatus(
            timestamp=now, trade_id=trade.id,
            trade_status_type_id=type_cache.trade_status_type_id("CANCELLED"),
        ))
        logger.info("Reconciliation: trade %s ERROR → CANCELLED (no orders filled)", trade.id)


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------


def run_exchange(
    exchange_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
    shutdown_event: threading.Event | None = None,
    exchange_cls: type[BaseExchange] | None = None,
) -> None:
    """Run an exchange as a long-running order-dispatch service.

    Subscribes to a Redis channel ``ascent.exchange.{exchange_id}`` and
    dispatches incoming order requests to the exchange implementation.
    A background monitor thread tracks open orders and publishes fill
    updates.

    Args:
        exchange_id: The database ID of the exchange.
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
        shutdown_event: Shared event for coordinated shutdown.
        exchange_cls: The exchange class (avoids import-by-ref).
    """
    from ascent.database.models.exchanges import Exchange as ExchangeModel
    from ascent.exchanges.base import BaseExchange as _Base

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)
    type_cache = TypeCache(session_factory)

    # Load exchange record
    with Session(engine) as db:
        record = db.get(ExchangeModel, exchange_id)
        if record is None:
            raise ValueError(f"Exchange {exchange_id} not found in database")
        config = record.config or {}
        exchange_name = record.name

    # Instantiate
    if exchange_cls is None:
        raise ValueError(
            f"Exchange {exchange_name}: no exchange class provided and "
            "import-by-ref is not supported for exchanges."
        )
    exchange_instance = exchange_cls(config)

    # Subscribe to order channel
    channel = f"ascent.exchange.{exchange_id}"
    pubsub = cache.subscribe([channel])

    shutdown = shutdown_event or threading.Event()

    if shutdown_event is None:

        def _signal_handler(signum, _frame):
            logger.info("Received signal %s, shutting down exchange %s", signum, exchange_name)
            shutdown.set()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

    # ------------------------------------------------------------------
    # Reconcile stale orders before starting loops
    # ------------------------------------------------------------------

    tracker = _OrderTracker()
    _reconcile(exchange_instance, exchange_id, tracker, session_factory, type_cache)

    # ------------------------------------------------------------------
    # Start monitor thread (auto-detect polling vs streaming)
    # ------------------------------------------------------------------

    has_streaming = type(exchange_instance).connect_order_stream is not _Base.connect_order_stream
    has_polling = type(exchange_instance).get_open_orders is not _Base.get_open_orders

    monitor_thread: threading.Thread | None = None
    if has_streaming:
        monitor_mode = "stream"
        monitor_thread = threading.Thread(
            target=_stream_monitor,
            args=(exchange_instance, cache, channel, str(exchange_id), tracker, shutdown),
            daemon=True,
            name=f"exchange-{exchange_name}-monitor",
        )
    elif has_polling:
        monitor_mode = "poll"
        monitor_thread = threading.Thread(
            target=_poll_monitor,
            args=(exchange_instance, cache, channel, str(exchange_id), tracker, shutdown),
            daemon=True,
            name=f"exchange-{exchange_name}-monitor",
        )
    else:
        monitor_mode = "none"

    if monitor_thread is not None:
        monitor_thread.start()

    logger.info(
        "Exchange %s (%s) listening on %s [monitor=%s]",
        exchange_name,
        exchange_id,
        channel,
        monitor_mode,
    )

    # ------------------------------------------------------------------
    # Dispatch loop (main thread)
    # ------------------------------------------------------------------

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        action = event.get("action")
        try:
            if action == "submit_order":
                from ascent.exchanges.base import OrderRequest

                request = OrderRequest(**event["order"])
                response = exchange_instance.submit_order(request)

                # Register with tracker so the monitor picks up fill updates
                tracker.track(
                    response.exchange_order_id,
                    order_id=event.get("order_id"),
                    trade_id=event.get("trade_id"),
                    trade_leg_id=event.get("trade_leg_id"),
                )

                logger.info(
                    "Order submitted: %s %s %s/%s qty=%s → %s",
                    response.exchange_order_id,
                    request.side,
                    request.from_asset_symbol,
                    request.to_asset_symbol,
                    request.quantity,
                    response.status,
                )

                # Publish immediate response with correlation IDs
                cache.publish(
                    f"{channel}.responses",
                    {
                        "action": "order_response",
                        "exchange_id": str(exchange_id),
                        "order_id": event.get("order_id"),
                        "trade_id": event.get("trade_id"),
                        "trade_leg_id": event.get("trade_leg_id"),
                        "response": response.model_dump(),
                    },
                )

            elif action == "cancel_order":
                exchange_order_id = event["exchange_order_id"]
                response = exchange_instance.cancel_order(exchange_order_id)
                meta = tracker.close(exchange_order_id)

                logger.info("Order cancelled: %s → %s", exchange_order_id, response.status)

                # Publish cancel response with correlation IDs
                _publish_update(
                    cache,
                    channel,
                    str(exchange_id),
                    meta or {},
                    response.model_dump(),
                )

            elif action == "get_balances":
                balances = exchange_instance.get_balances()
                logger.info("Balances: %d assets", len(balances))

            else:
                logger.warning("Unknown action '%s' on exchange %s", action, exchange_name)

        except Exception:
            logger.exception("Error processing %s on exchange %s", action, exchange_name)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    if monitor_thread is not None:
        monitor_thread.join(timeout=5.0)

    pubsub.close()
    logger.info("Exchange %s shut down cleanly", exchange_name)
