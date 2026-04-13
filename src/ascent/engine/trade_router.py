"""Routes trade requests from strategies to exchanges, persisting all records."""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.engine.cache import EngineCache
from ascent.engine.type_cache import TypeCache

logger = logging.getLogger(__name__)


class TradeRouter:
    """Dispatches orders to exchanges, creating Trade/TradeLeg/Order records.

    Created per-strategy by the consumer with all necessary context.
    """

    def __init__(
        self,
        cache: EngineCache,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        exchange_map: dict[uuid.UUID, dict],
        session_factory: sessionmaker,
        type_cache: TypeCache,
        is_paper: bool = False,
    ) -> None:
        self._cache = cache
        self._strategy_id = strategy_id
        self._portfolio_id = portfolio_id
        self._exchange_map = exchange_map
        self._session_factory = session_factory
        self._type_cache = type_cache
        self._is_paper = is_paper
        self._strategy_run_id: uuid.UUID | None = None

    def _pick_exchange(self) -> tuple[uuid.UUID, dict]:
        """Select the first active exchange."""
        for eid, info in self._exchange_map.items():
            if info.get("is_active", True):
                return eid, info
        raise RuntimeError(
            "No active exchange available. Make sure at least one exchange "
            "is deployed, active, and linked to the strategy."
        )

    def _resolve_legs(
        self,
        target_id: uuid.UUID,
        scope: Literal["instrument", "composite"],
        side: str,
        quantity: float,
        db: Session,
    ) -> list[dict]:
        """Resolve a target UUID to one or more trade legs.

        Args:
            target_id: Instrument or Composite UUID.
            scope: ``"instrument"`` or ``"composite"``.
            side: ``"BUY"`` or ``"SELL"``.
            quantity: Units per leg.
        """
        if scope == "composite":
            from ascent.database.models.composites import Composite, CompositeMember

            composite = db.get(Composite, target_id)
            if composite is None:
                raise ValueError(f"Composite {target_id} not found in database")

            members = (
                db.execute(
                    select(CompositeMember)
                    .where(CompositeMember.composite_id == composite.id)
                    .order_by(CompositeMember.order)
                )
                .scalars()
                .all()
            )
            if not members:
                raise ValueError(f"Composite '{composite.name}' has no member instruments")

            legs = []
            for i, member in enumerate(members):
                if i == 0:
                    direction = "LONG" if side == "BUY" else "SHORT"
                else:
                    direction = "SHORT" if side == "BUY" else "LONG"
                leg_side = "BUY" if direction == "LONG" else "SELL"
                legs.append(
                    {
                        "instrument_id": member.instrument_id,
                        "direction": direction,
                        "side": leg_side,
                        "quantity": quantity,
                    }
                )
            return legs

        # scope == "instrument"
        from ascent.database.models.instruments import Instrument

        if db.get(Instrument, target_id) is None:
            raise ValueError(f"Instrument {target_id} not found in database")

        direction = "LONG" if side == "BUY" else "SHORT"
        return [
            {
                "instrument_id": target_id,
                "direction": direction,
                "side": side,
                "quantity": quantity,
            }
        ]

    def submit(
        self,
        *,
        side: str,
        target_id: uuid.UUID,
        scope: Literal["instrument", "composite"] = "instrument",
        quantity: float,
        price: float | None = None,
        order_type: str = "MARKET",
    ) -> dict:
        """Create Trade + TradeLeg + Order records and route to the exchange.

        Args:
            side: ``BUY`` or ``SELL``.
            target_id: Instrument or Composite UUID.
            scope: ``instrument`` or ``composite``.
            quantity: Units per leg.
            price: Limit price. None for market.
            order_type: ``MARKET`` or ``LIMIT``.

        Returns a dict with trade_id, status, and per-leg details.
        """
        from ascent.database.models.orders import Order, OrderStatus
        from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

        exchange_id, exchange_info = self._pick_exchange()
        channel = exchange_info["channel"]
        now = datetime.datetime.now(tz=datetime.UTC)

        with Session(bind=self._session_factory.kw["bind"]) as db:
            # Resolve legs
            legs = self._resolve_legs(target_id, scope, side, quantity, db)

            # Create Trade
            trade = Trade(
                strategy_id=self._strategy_id,
                strategy_run_id=self._strategy_run_id,
                portfolio_id=self._portfolio_id,
                is_paper=self._is_paper,
                entry_at=now,
                current_status_type_id=self._type_cache.trade_status_type_id("PENDING"),
            )
            db.add(trade)
            db.flush()

            # Trade status: PENDING
            db.add(
                TradeStatus(
                    timestamp=now,
                    trade_id=trade.id,
                    trade_status_type_id=self._type_cache.trade_status_type_id("PENDING"),
                )
            )

            order_type_id = self._type_cache.order_type_id(order_type)
            submitted_status_id = self._type_cache.order_status_type_id("SUBMITTED")

            leg_records = []
            order_records = []

            for leg_data in legs:
                # Create TradeLeg
                trade_leg = TradeLeg(
                    trade_id=trade.id,
                    instrument_id=leg_data["instrument_id"],
                    direction=leg_data["direction"],
                    quantity=leg_data["quantity"],
                    expected_entry_price=price,
                    exchange_id=exchange_id,
                )
                db.add(trade_leg)
                db.flush()

                # Create Order
                order = Order(
                    timestamp=now,
                    order_type_id=order_type_id,
                    side=leg_data["side"],
                    exchange_id=exchange_id,
                    portfolio_id=self._portfolio_id,
                    instrument_id=leg_data["instrument_id"],
                    quantity=leg_data["quantity"],
                    price=price or 0.0,
                    trade_leg_id=trade_leg.id,
                )
                db.add(order)
                db.flush()

                # Order status: SUBMITTED
                db.add(
                    OrderStatus(
                        timestamp=now,
                        order_id=order.id,
                        order_status_type_id=submitted_status_id,
                    )
                )

                trade_leg.entry_order_id = order.id
                leg_records.append(trade_leg)
                order_records.append(order)

            # Trade status: OPENING (offset by 1μs to avoid PK collision with PENDING)
            trade.current_status_type_id = self._type_cache.trade_status_type_id("OPENING")
            db.add(
                TradeStatus(
                    timestamp=now + datetime.timedelta(microseconds=1),
                    trade_id=trade.id,
                    trade_status_type_id=self._type_cache.trade_status_type_id("OPENING"),
                )
            )
            db.commit()

            # Collect IDs for Redis + response
            trade_id = trade.id
            leg_details = [
                {
                    "trade_leg_id": str(leg.id),
                    "instrument_id": str(leg.instrument_id),
                    "order_id": str(order.id),
                    "direction": leg.direction,
                    "side": legs[i]["side"],
                    "quantity": leg.quantity,
                }
                for i, (leg, order) in enumerate(zip(leg_records, order_records, strict=False))
            ]

        # Publish orders to exchange
        for i, (leg, order) in enumerate(zip(leg_records, order_records, strict=False)):
            order_payload = {
                "action": "submit_order",
                "strategy_id": str(self._strategy_id),
                "order_id": str(order.id),
                "trade_id": str(trade_id),
                "trade_leg_id": str(leg.id),
                "order": {
                    "order_type": order_type,
                    "side": legs[i]["side"],
                    "from_asset_symbol": str(leg.instrument_id),
                    "to_asset_symbol": "USD",
                    "quantity": leg.quantity,
                    "price": price,
                    "client_order_id": str(order.id),
                },
            }
            self._cache.publish(channel, order_payload)

        # Wait for exchange responses
        response_channel = f"{channel}.responses"
        response_pubsub = self._cache.subscribe([response_channel])
        pending_order_ids = {str(o.id) for o in order_records}
        filled_orders: dict[str, dict] = {}
        timeout_at = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=5)

        while pending_order_ids and datetime.datetime.now(tz=datetime.UTC) < timeout_at:
            resp = self._cache.poll(response_pubsub, timeout=0.5)
            if resp is None:
                continue
            resp_order_id = resp.get("order_id")
            if resp_order_id in pending_order_ids:
                pending_order_ids.discard(resp_order_id)
                filled_orders[resp_order_id] = resp.get("response", {})

        response_pubsub.close()

        # Process fills
        trade_status = "OPENING"
        with Session(bind=self._session_factory.kw["bind"]) as db:
            now_fill = datetime.datetime.now(tz=datetime.UTC)
            all_filled = True

            for leg, order in zip(leg_records, order_records, strict=False):
                fill = filled_orders.get(str(order.id))
                if fill and fill.get("status") == "FILLED":
                    # Update Order
                    db_order = db.get(Order, order.id)
                    db_order.filled_quantity = fill.get("filled_quantity", 0.0)
                    db_order.average_fill_price = fill.get("average_fill_price")
                    db_order.external_order_id = fill.get("exchange_order_id")

                    db.add(
                        OrderStatus(
                            timestamp=now_fill,
                            order_id=order.id,
                            order_status_type_id=self._type_cache.order_status_type_id("FILLED"),
                        )
                    )

                    # Update TradeLeg
                    db_leg = db.get(TradeLeg, leg.id)
                    db_leg.entry_price = fill.get("average_fill_price") or price

                    logger.info(
                        "Order %s filled: %s qty=%.4f @ %.4f",
                        order.id,
                        legs[order_records.index(order)]["side"],
                        fill.get("filled_quantity", 0.0),
                        fill.get("average_fill_price", 0.0),
                    )
                elif fill and fill.get("status") == "REJECTED":
                    db.add(
                        OrderStatus(
                            timestamp=now_fill,
                            order_id=order.id,
                            order_status_type_id=self._type_cache.order_status_type_id("REJECTED"),
                            error_message=fill.get("error_message"),
                        )
                    )
                    all_filled = False
                    logger.warning("Order %s rejected: %s", order.id, fill.get("error_message"))
                else:
                    all_filled = False

            # Update Trade status
            db_trade = db.get(Trade, trade_id)
            if all_filled:
                db_trade.current_status_type_id = self._type_cache.trade_status_type_id("OPEN")
                db.add(
                    TradeStatus(
                        timestamp=now_fill,
                        trade_id=trade_id,
                        trade_status_type_id=self._type_cache.trade_status_type_id("OPEN"),
                    )
                )
                trade_status = "OPEN"
                logger.info("Trade %s is OPEN (%d legs filled)", trade_id, len(leg_records))
            elif filled_orders:
                db_trade.current_status_type_id = self._type_cache.trade_status_type_id("ERROR")
                db.add(
                    TradeStatus(
                        timestamp=now_fill,
                        trade_id=trade_id,
                        trade_status_type_id=self._type_cache.trade_status_type_id("ERROR"),
                    )
                )
                trade_status = "ERROR"

            db.commit()

        return {
            "trade_id": str(trade_id),
            "status": trade_status,
            "legs": leg_details,
        }

    def get_open_trades(self) -> list[dict]:
        """Return all OPEN trades for this strategy with leg details."""
        from ascent.database.models.trades import Trade, TradeLeg

        open_status_id = self._type_cache.trade_status_type_id("OPEN")

        with Session(bind=self._session_factory.kw["bind"]) as db:
            trades = (
                db.execute(
                    select(Trade).where(
                        Trade.strategy_id == self._strategy_id,
                        Trade.current_status_type_id == open_status_id,
                    )
                )
                .scalars()
                .all()
            )
            results = []
            for t in trades:
                legs = db.execute(select(TradeLeg).where(TradeLeg.trade_id == t.id)).scalars().all()
                results.append(
                    {
                        "trade_id": str(t.id),
                        "entry_at": t.entry_at.isoformat() if t.entry_at else None,
                        "is_paper": t.is_paper,
                        "legs": [
                            {
                                "instrument_id": str(leg.instrument_id),
                                "direction": leg.direction,
                                "quantity": leg.quantity,
                                "entry_price": leg.entry_price,
                            }
                            for leg in legs
                        ],
                    }
                )
            return results

    def close(
        self,
        *,
        trade_id: uuid.UUID,
        price: float | None = None,
        close_reason: str = "MODEL_SIGNAL",
    ) -> dict:
        """Close an open trade by submitting exit orders for all legs.

        Returns a dict with trade_id and status.
        """
        from ascent.database.models.orders import Order, OrderStatus
        from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

        exchange_id, exchange_info = self._pick_exchange()
        channel = exchange_info["channel"]
        now = datetime.datetime.now(tz=datetime.UTC)

        with Session(bind=self._session_factory.kw["bind"]) as db:
            trade = db.get(Trade, trade_id)
            if trade is None:
                raise ValueError(f"Trade {trade_id} not found")

            open_status_id = self._type_cache.trade_status_type_id("OPEN")
            if trade.current_status_type_id != open_status_id:
                raise ValueError(f"Trade {trade_id} is not OPEN")

            # Load legs
            legs = db.execute(select(TradeLeg).where(TradeLeg.trade_id == trade_id)).scalars().all()
            if not legs:
                raise ValueError(f"Trade {trade_id} has no legs")

            # Trade status: CLOSING
            trade.current_status_type_id = self._type_cache.trade_status_type_id("CLOSING")
            db.add(
                TradeStatus(
                    timestamp=now,
                    trade_id=trade_id,
                    trade_status_type_id=self._type_cache.trade_status_type_id("CLOSING"),
                )
            )

            order_type_id = self._type_cache.order_type_id("MARKET")
            submitted_status_id = self._type_cache.order_status_type_id("SUBMITTED")

            exit_orders: list[dict] = []
            for leg in legs:
                exit_side = "SELL" if leg.direction == "LONG" else "BUY"

                order = Order(
                    timestamp=now,
                    order_type_id=order_type_id,
                    side=exit_side,
                    exchange_id=leg.exchange_id or exchange_id,
                    portfolio_id=self._portfolio_id,
                    instrument_id=leg.instrument_id,
                    quantity=leg.quantity,
                    price=price or 0.0,
                    trade_leg_id=leg.id,
                )
                db.add(order)
                db.flush()

                db.add(
                    OrderStatus(
                        timestamp=now,
                        order_id=order.id,
                        order_status_type_id=submitted_status_id,
                    )
                )

                leg.exit_order_id = order.id
                if price:
                    leg.expected_exit_price = price

                # Capture all needed data as plain values before session closes
                exit_orders.append(
                    {
                        "order_id": order.id,
                        "leg_id": leg.id,
                        "instrument_id": leg.instrument_id,
                        "direction": leg.direction,
                        "quantity": leg.quantity,
                        "entry_price": leg.entry_price,
                        "side": exit_side,
                    }
                )

            db.commit()

        # Publish exit orders to exchange
        for eo in exit_orders:
            self._cache.publish(
                channel,
                {
                    "action": "submit_order",
                    "strategy_id": str(self._strategy_id),
                    "order_id": str(eo["order_id"]),
                    "trade_id": str(trade_id),
                    "trade_leg_id": str(eo["leg_id"]),
                    "order": {
                        "order_type": "MARKET",
                        "side": eo["side"],
                        "from_asset_symbol": str(eo["instrument_id"]),
                        "to_asset_symbol": "USD",
                        "quantity": eo["quantity"],
                        "price": price,
                        "client_order_id": str(eo["order_id"]),
                    },
                },
            )

        # Wait for responses
        response_channel = f"{channel}.responses"
        response_pubsub = self._cache.subscribe([response_channel])
        pending = {str(eo["order_id"]) for eo in exit_orders}
        fills: dict[str, dict] = {}
        timeout_at = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=5)

        while pending and datetime.datetime.now(tz=datetime.UTC) < timeout_at:
            resp = self._cache.poll(response_pubsub, timeout=0.5)
            if resp is None:
                continue
            oid = resp.get("order_id")
            if oid in pending:
                pending.discard(oid)
                fills[oid] = resp.get("response", {})

        response_pubsub.close()

        # Process fills and close trade
        trade_status = "CLOSING"
        with Session(bind=self._session_factory.kw["bind"]) as db:
            now_fill = datetime.datetime.now(tz=datetime.UTC)
            all_filled = True
            total_pnl = 0.0

            for eo in exit_orders:
                fill = fills.get(str(eo["order_id"]))
                if fill and fill.get("status") == "FILLED":
                    db_order = db.get(Order, eo["order_id"])
                    db_order.filled_quantity = fill.get("filled_quantity", 0.0)
                    db_order.average_fill_price = fill.get("average_fill_price")
                    db_order.external_order_id = fill.get("exchange_order_id")

                    db.add(
                        OrderStatus(
                            timestamp=now_fill,
                            order_id=eo["order_id"],
                            order_status_type_id=self._type_cache.order_status_type_id("FILLED"),
                        )
                    )

                    db_leg = db.get(TradeLeg, eo["leg_id"])
                    exit_price = fill.get("average_fill_price") or price or 0.0
                    db_leg.exit_price = exit_price

                    # Compute PnL
                    entry = eo["entry_price"] or 0.0
                    if eo["direction"] == "LONG":
                        pnl = (exit_price - entry) * eo["quantity"]
                    else:
                        pnl = (entry - exit_price) * eo["quantity"]
                    db_leg.realized_pnl = round(pnl, 6)
                    total_pnl += pnl

                    logger.info(
                        "Exit order %s filled: %s qty=%.4f @ %.4f  pnl=%.4f",
                        eo["order_id"],
                        eo["side"],
                        fill.get("filled_quantity", 0.0),
                        exit_price,
                        pnl,
                    )
                else:
                    all_filled = False

            db_trade = db.get(Trade, trade_id)
            if all_filled:
                db_trade.current_status_type_id = self._type_cache.trade_status_type_id("CLOSED")
                db_trade.exit_at = now_fill
                db_trade.close_reason = close_reason
                db_trade.total_realized_pnl = round(total_pnl, 6)
                db.add(
                    TradeStatus(
                        timestamp=now_fill,
                        trade_id=trade_id,
                        trade_status_type_id=self._type_cache.trade_status_type_id("CLOSED"),
                    )
                )
                trade_status = "CLOSED"
                logger.info(
                    "Trade %s CLOSED  pnl=%.4f  reason=%s",
                    trade_id,
                    total_pnl,
                    close_reason,
                )

            db.commit()

        return {
            "trade_id": str(trade_id),
            "status": trade_status,
            "total_pnl": round(total_pnl, 6) if trade_status == "CLOSED" else None,
        }
