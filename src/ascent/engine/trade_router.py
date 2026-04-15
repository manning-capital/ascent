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

    def _await_acks(
        self, channel: str, order_records: list, timeout_seconds: float = 5.0
    ) -> dict[str, dict]:
        """Wait for initial exchange acknowledgements (SUBMITTED responses).

        Returns a dict mapping ``order_id`` → response payload for each
        order that was acknowledged within the timeout.
        """
        response_channel = f"{channel}.responses"
        response_pubsub = self._cache.subscribe([response_channel])
        pending = {str(o.id) for o in order_records}
        acks: dict[str, dict] = {}
        timeout_at = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(
            seconds=timeout_seconds
        )

        while pending and datetime.datetime.now(tz=datetime.UTC) < timeout_at:
            resp = self._cache.poll(response_pubsub, timeout=0.5)
            if resp is None:
                continue
            if resp.get("action") != "order_response":
                continue
            resp_order_id = resp.get("order_id")
            if resp_order_id in pending:
                pending.discard(resp_order_id)
                acks[resp_order_id] = resp.get("response", {})

        response_pubsub.close()

        if pending:
            logger.warning(
                "Timed out waiting for exchange ack on %d order(s): %s",
                len(pending),
                pending,
            )

        return acks

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

        # Wait for initial exchange acknowledgements to capture exchange_order_id.
        # The exchange returns SUBMITTED immediately; actual fills arrive later
        # via the fill handler.
        ack_orders = self._await_acks(channel, order_records)

        # Persist the exchange-assigned order IDs
        with Session(bind=self._session_factory.kw["bind"]) as db:
            for order in order_records:
                ack = ack_orders.get(str(order.id))
                if ack:
                    db_order = db.get(Order, order.id)
                    if ack.get("exchange_order_id"):
                        db_order.external_order_id = ack["exchange_order_id"]
                    # Handle immediate rejection
                    if ack.get("status") == "REJECTED":
                        db.add(
                            OrderStatus(
                                timestamp=datetime.datetime.now(tz=datetime.UTC),
                                order_id=order.id,
                                order_status_type_id=self._type_cache.order_status_type_id(
                                    "REJECTED"
                                ),
                                error_message=ack.get("error_message"),
                            )
                        )
                        logger.warning(
                            "Order %s rejected: %s", order.id, ack.get("error_message")
                        )
            db.commit()

        # Notify the UI that a new trade exists
        self._cache.publish(
            "ascent.trades.updates",
            {"event": "trade_created", "trade_id": str(trade_id)},
        )

        return {
            "trade_id": str(trade_id),
            "status": "OPENING",
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

        # Wait for initial exchange acknowledgements to capture exchange_order_id.
        # Actual fills arrive asynchronously via the fill handler.
        ack_orders = self._await_acks(channel, [
            type("_O", (), {"id": eo["order_id"]}) for eo in exit_orders
        ])

        # Persist exchange-assigned order IDs
        with Session(bind=self._session_factory.kw["bind"]) as db:
            for eo in exit_orders:
                ack = ack_orders.get(str(eo["order_id"]))
                if ack and ack.get("exchange_order_id"):
                    db_order = db.get(Order, eo["order_id"])
                    db_order.external_order_id = ack["exchange_order_id"]
            db.commit()

        # Notify the UI that the trade is closing
        self._cache.publish(
            "ascent.trades.updates",
            {"event": "trade_closing", "trade_id": str(trade_id)},
        )

        return {
            "trade_id": str(trade_id),
            "status": "CLOSING",
        }
