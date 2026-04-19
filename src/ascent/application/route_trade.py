"""TradeRouter use case — creates Trade + TradeLeg + Order records and publishes orders.

Every write path runs inside a single :class:`UnitOfWork` so the trade
row, order rows, and dispatch-intent outbox entries land in one atomic
transaction. The UI notification (non-critical) publishes after commit
through the best-effort event bus.

Replaces the old ``ascent.engine.trade_router.TradeRouter`` with an async-first
design that takes explicit dependencies. Exchange acks arrive asynchronously
through the event bus and are handled by the fill-processor pipeline.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ascent.domain import Direction, OrderType, TradeState
from ascent.ports import (
    EventBus,
    OrderRepository,
    OutboxPublisher,
    RouteGate,
    TradeRepository,
    UnitOfWorkFactory,
)
from ascent.ports.trade_repo import NewLegSpec, NewOrderSpec

logger = logging.getLogger(__name__)

UI_CHANNEL = "ascent.trades.updates"


class _AlwaysAllowRouteGate(RouteGate):
    """No-op gate used when no real gate is wired (tests, legacy callers)."""

    async def validate_open(
        self, session, *, strategy_id, exchange_id, instrument_ids
    ) -> str | None:
        return None


@dataclass(frozen=True)
class ExchangeBinding:
    exchange_id: uuid.UUID
    channel: str


@dataclass(frozen=True)
class CompositeSpec:
    """Resolved composite membership. The evaluate-strategy use case loads these."""

    composite_id: uuid.UUID
    ordered_instrument_ids: list[uuid.UUID]


@dataclass(frozen=True)
class TradeDraft:
    trade_id: uuid.UUID
    state: TradeState
    leg_summaries: list[dict]


@dataclass(frozen=True)
class _EntryOrder:
    """Bundles everything we need to publish an exchange order after the
    Trade/Leg/Order rows are persisted.
    """

    leg_id: uuid.UUID
    order_id: uuid.UUID
    side: str
    quantity: float
    instrument_id: uuid.UUID


class TradeRouter:
    def __init__(
        self,
        *,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        trade_repo: TradeRepository,
        order_repo: OrderRepository,
        event_bus: EventBus,
        outbox: OutboxPublisher,
        uow_factory: UnitOfWorkFactory,
        exchanges: list[ExchangeBinding],
        route_gate: RouteGate | None = None,
        is_paper: bool = False,
    ) -> None:
        if not exchanges:
            raise ValueError("TradeRouter requires at least one exchange binding")
        self._strategy_id = strategy_id
        self._portfolio_id = portfolio_id
        self._trades = trade_repo
        self._orders = order_repo
        self._bus = event_bus
        self._outbox = outbox
        self._uow_factory = uow_factory
        self._exchanges = exchanges
        self._route_gate: RouteGate = route_gate or _AlwaysAllowRouteGate()
        self._is_paper = is_paper
        self._strategy_run_id: uuid.UUID | None = None

    def bind_strategy_run(self, strategy_run_id: uuid.UUID) -> None:
        """Set the current strategy-run id for trade provenance stamping."""
        self._strategy_run_id = strategy_run_id

    async def submit(
        self,
        *,
        side: Literal["BUY", "SELL"],
        target_id: uuid.UUID,
        scope: Literal["instrument", "composite"] = "instrument",
        quantity: float,
        now: datetime,
        price: float | None = None,
        order_type: OrderType = OrderType.MARKET,
        composite: CompositeSpec | None = None,
    ) -> TradeDraft:
        """Open a new trade.

        For ``scope='composite'``, ``composite`` must supply the ordered
        instrument membership; the router creates one leg per instrument.

        The route gate runs before any DB write. If the gate rejects, a
        terminal :class:`TradeState.REJECTED` ``Trade`` row is persisted with
        ``close_reason='UNIVERSE_SCOPE:<code>'`` and the returned
        :class:`TradeDraft` carries ``state=REJECTED``. No orders, legs, or
        outbox entries are produced.
        """
        binding = self._exchanges[0]
        validate_instruments = self._instruments_for_validation(scope, target_id, composite)

        async with self._uow_factory() as uow:
            rejection = await self._route_gate.validate_open(
                uow.session,
                strategy_id=self._strategy_id,
                exchange_id=binding.exchange_id,
                instrument_ids=validate_instruments,
            )

            if rejection is not None:
                trade = await self._trades.create(
                    uow.session,
                    strategy_id=self._strategy_id,
                    portfolio_id=self._portfolio_id,
                    is_paper=self._is_paper,
                    entry_at=now,
                    strategy_run_id=self._strategy_run_id,
                    legs=[],
                )
                await self._trades.set_state(
                    uow.session,
                    trade.id,
                    new_state=TradeState.REJECTED,
                    at=now,
                    close_reason=f"UNIVERSE_SCOPE:{rejection}",
                )
                rejected_trade_id = trade.id
            else:
                leg_specs = self._build_leg_specs(
                    side=side,
                    target_id=target_id,
                    scope=scope,
                    quantity=quantity,
                    price=price,
                    exchange_id=binding.exchange_id,
                    composite=composite,
                )
                trade = await self._trades.create(
                    uow.session,
                    strategy_id=self._strategy_id,
                    portfolio_id=self._portfolio_id,
                    is_paper=self._is_paper,
                    entry_at=now,
                    strategy_run_id=self._strategy_run_id,
                    legs=leg_specs,
                )

                entry_orders: list[_EntryOrder] = []
                for leg, spec in zip(trade.legs, leg_specs, strict=True):
                    order_side = "BUY" if spec.direction == Direction.LONG else "SELL"
                    order = await self._orders.create(
                        uow.session,
                        NewOrderSpec(
                            timestamp=now,
                            order_type=order_type,
                            side=order_side,
                            quantity=spec.quantity,
                            price=price or 0.0,
                            exchange_id=binding.exchange_id,
                            portfolio_id=self._portfolio_id,
                            instrument_id=spec.instrument_id,
                            trade_leg_id=leg.id,
                        ),
                    )
                    await self._trades.set_entry_order(uow.session, leg.id, order.id)
                    entry_orders.append(
                        _EntryOrder(
                            leg_id=leg.id,
                            order_id=order.id,
                            side=order_side,
                            quantity=spec.quantity,
                            instrument_id=spec.instrument_id,
                        )
                    )

                await self._trades.set_state(
                    uow.session, trade.id, new_state=TradeState.OPENING, at=now
                )

                # Durable dispatch: enqueue each entry order to the outbox,
                # atomically with the trade/order rows. The relay forwards these
                # to the broker; the exchange dispatcher consumes from there.
                for entry in entry_orders:
                    await self._outbox.enqueue(
                        uow.session,
                        channel=binding.channel,
                        subject=binding.channel,
                        payload={
                            "action": "submit_order",
                            "strategy_id": str(self._strategy_id),
                            "order_id": str(entry.order_id),
                            "trade_id": str(trade.id),
                            "trade_leg_id": str(entry.leg_id),
                            "order": {
                                "order_type": order_type.value,
                                "side": entry.side,
                                "from_asset_symbol": str(entry.instrument_id),
                                "to_asset_symbol": "USD",
                                "quantity": entry.quantity,
                                "price": price,
                                "client_order_id": str(entry.order_id),
                            },
                        },
                    )

        # Post-commit: UI ping is best-effort and explicitly non-durable.
        if rejection is not None:
            await self._bus.publish(
                UI_CHANNEL,
                {"event": "trade_rejected", "trade_id": str(rejected_trade_id), "reason": rejection},
            )
            return TradeDraft(
                trade_id=rejected_trade_id,
                state=TradeState.REJECTED,
                leg_summaries=[],
            )

        await self._bus.publish(UI_CHANNEL, {"event": "trade_created", "trade_id": str(trade.id)})

        return TradeDraft(
            trade_id=trade.id,
            state=TradeState.OPENING,
            leg_summaries=[
                {
                    "trade_leg_id": str(entry.leg_id),
                    "order_id": str(entry.order_id),
                    "side": entry.side,
                }
                for entry in entry_orders
            ],
        )

    @staticmethod
    def _instruments_for_validation(
        scope: str,
        target_id: uuid.UUID,
        composite: CompositeSpec | None,
    ) -> list[uuid.UUID]:
        """Per-leg instrument list the gate validates. Composites are atomic:
        if any member fails the gate, the whole composite is rejected."""
        if scope == "composite":
            if composite is None:
                raise ValueError("composite scope requires a CompositeSpec")
            return list(composite.ordered_instrument_ids)
        return [target_id]

    async def close(
        self,
        *,
        trade_id: uuid.UUID,
        now: datetime,
        price: float | None = None,
        order_type: OrderType = OrderType.MARKET,
        close_reason: str | None = None,
    ) -> TradeDraft:
        binding = self._exchanges[0]
        exit_orders: list[_EntryOrder] = []

        async with self._uow_factory() as uow:
            trade = await self._trades.get(uow.session, trade_id)
            if trade is None:
                raise ValueError(f"Trade {trade_id} not found")
            if trade.state != TradeState.OPEN:
                raise ValueError(f"Trade {trade_id} is not OPEN (state={trade.state.value})")

            for leg in trade.legs:
                exit_side = "SELL" if leg.direction == Direction.LONG else "BUY"
                order = await self._orders.create(
                    uow.session,
                    NewOrderSpec(
                        timestamp=now,
                        order_type=order_type,
                        side=exit_side,
                        quantity=leg.quantity,
                        price=price or 0.0,
                        exchange_id=binding.exchange_id,
                        portfolio_id=self._portfolio_id,
                        instrument_id=leg.instrument_id,
                        trade_leg_id=leg.id,
                    ),
                )
                await self._trades.set_exit_order(uow.session, leg.id, order.id)
                exit_orders.append(
                    _EntryOrder(
                        leg_id=leg.id,
                        order_id=order.id,
                        side=exit_side,
                        quantity=leg.quantity,
                        instrument_id=leg.instrument_id,
                    )
                )

            await self._trades.set_state(
                uow.session,
                trade_id,
                new_state=TradeState.CLOSING,
                at=now,
                close_reason=close_reason,
            )

            for exit_ in exit_orders:
                await self._outbox.enqueue(
                    uow.session,
                    channel=binding.channel,
                    subject=binding.channel,
                    payload={
                        "action": "submit_order",
                        "strategy_id": str(self._strategy_id),
                        "order_id": str(exit_.order_id),
                        "trade_id": str(trade_id),
                        "trade_leg_id": str(exit_.leg_id),
                        "order": {
                            "order_type": order_type.value,
                            "side": exit_.side,
                            "from_asset_symbol": str(exit_.instrument_id),
                            "to_asset_symbol": "USD",
                            "quantity": exit_.quantity,
                            "price": price,
                            "client_order_id": str(exit_.order_id),
                        },
                    },
                )

        await self._bus.publish(UI_CHANNEL, {"event": "trade_closing", "trade_id": str(trade_id)})

        return TradeDraft(
            trade_id=trade_id,
            state=TradeState.CLOSING,
            leg_summaries=[
                {
                    "trade_leg_id": str(exit_.leg_id),
                    "order_id": str(exit_.order_id),
                    "side": exit_.side,
                }
                for exit_ in exit_orders
            ],
        )

    async def get_open_trades(self) -> list[dict]:
        async with self._uow_factory() as uow:
            trades = await self._trades.list_open_for_strategy(uow.session, self._strategy_id)
        return [
            {
                "trade_id": str(t.id),
                "entry_at": t.entry_at.isoformat() if t.entry_at else None,
                "is_paper": t.is_paper,
                "legs": [
                    {
                        "instrument_id": str(leg.instrument_id),
                        "direction": leg.direction.value,
                        "quantity": leg.quantity,
                        "entry_price": leg.entry_price,
                    }
                    for leg in t.legs
                ],
            }
            for t in trades
        ]

    # ---- internal ----

    def _build_leg_specs(
        self,
        *,
        side: str,
        target_id: uuid.UUID,
        scope: str,
        quantity: float,
        price: float | None,
        exchange_id: uuid.UUID,
        composite: CompositeSpec | None,
    ) -> list[NewLegSpec]:
        if scope == "composite":
            if composite is None:
                raise ValueError("composite scope requires a CompositeSpec")
            legs = []
            for i, instrument_id in enumerate(composite.ordered_instrument_ids):
                if i == 0:
                    direction = Direction.LONG if side == "BUY" else Direction.SHORT
                else:
                    direction = Direction.SHORT if side == "BUY" else Direction.LONG
                legs.append(
                    NewLegSpec(
                        instrument_id=instrument_id,
                        direction=direction,
                        quantity=quantity,
                        expected_entry_price=price,
                        exchange_id=exchange_id,
                    )
                )
            return legs

        direction = Direction.LONG if side == "BUY" else Direction.SHORT
        return [
            NewLegSpec(
                instrument_id=target_id,
                direction=direction,
                quantity=quantity,
                expected_entry_price=price,
                exchange_id=exchange_id,
            )
        ]
