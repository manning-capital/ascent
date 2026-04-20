"""Dict-backed in-memory repositories for domain types.

Every method accepts a ``session`` parameter (for interface parity with the
SQL adapter) and ignores it. The fakes have no transaction — they commit
immediately to their dict store. Tests that want rollback semantics use
:class:`SqlAlchemyUnitOfWork` against a real DB; these fakes verify only
the shape of the interactions.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from typing import Any

from ascent.domain import (
    Order,
    OrderSide,
    OrderState,
    Trade,
    TradeLeg,
    TradeState,
)
from ascent.ports import (
    FeedRunRepository,
    OrderRepository,
    StrategyRunRepository,
    StrategyUniverseRepository,
    TradeRepository,
)
from ascent.ports.strategy_universe import Scope
from ascent.ports.trade_repo import NewLegSpec, NewOrderSpec


class InMemoryStrategyUniverseRepository(StrategyUniverseRepository):
    """Returns the configured active universe for each (strategy_id, scope) tuple.

    Tests that don't care about universe filtering can leave this empty — the
    evaluator will produce an empty context (which is what the trade-only
    fixtures expect).
    """

    def __init__(self) -> None:
        self._instrument_universe: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._composite_universe: dict[uuid.UUID, set[uuid.UUID]] = {}

    def set_instrument_universe(
        self, strategy_id: uuid.UUID, instrument_ids: set[uuid.UUID]
    ) -> None:
        self._instrument_universe[strategy_id] = set(instrument_ids)

    def set_composite_universe(
        self, strategy_id: uuid.UUID, composite_ids: set[uuid.UUID]
    ) -> None:
        self._composite_universe[strategy_id] = set(composite_ids)

    async def get_active_universe(
        self, session: Any, strategy_id: uuid.UUID, scope: Scope
    ) -> set[uuid.UUID]:
        if scope == "composite":
            return set(self._composite_universe.get(strategy_id, set()))
        return set(self._instrument_universe.get(strategy_id, set()))


class InMemoryTradeRepository(TradeRepository):
    def __init__(self) -> None:
        self._trades: dict[uuid.UUID, Trade] = {}
        self._entry_order_of: dict[uuid.UUID, uuid.UUID] = {}  # leg_id → order_id
        self._exit_order_of: dict[uuid.UUID, uuid.UUID] = {}
        self.close_reasons: dict[uuid.UUID, str] = {}
        self._order_repo: InMemoryOrderRepository | None = None

    def link_order_repo(self, order_repo: InMemoryOrderRepository) -> None:
        """Wire an order repo so ``get()`` can return legs with live order state."""
        self._order_repo = order_repo

    async def get(self, session: Any, trade_id: uuid.UUID) -> Trade | None:
        trade = self._trades.get(trade_id)
        return None if trade is None else self._materialize(trade)

    async def list_non_terminal_for_strategy(
        self, session: Any, strategy_id: uuid.UUID
    ) -> list[Trade]:
        return [
            self._materialize(t)
            for t in self._trades.values()
            if t.strategy_id == strategy_id and not t.state.is_terminal
        ]

    async def list_open_for_strategy(self, session: Any, strategy_id: uuid.UUID) -> list[Trade]:
        return [
            self._materialize(t)
            for t in self._trades.values()
            if t.strategy_id == strategy_id and t.state == TradeState.OPEN
        ]

    def _materialize(self, trade: Trade) -> Trade:
        new_legs = []
        for leg in trade.legs:
            entry_order_id = self._entry_order_of.get(leg.id)
            exit_order_id = self._exit_order_of.get(leg.id)
            entry_order = (
                self._resolve_order(entry_order_id)
                if entry_order_id is not None
                else leg.entry_order
            )
            exit_order = (
                self._resolve_order(exit_order_id) if exit_order_id is not None else leg.exit_order
            )
            new_legs.append(replace(leg, entry_order=entry_order, exit_order=exit_order))
        return replace(trade, legs=tuple(new_legs))

    def _resolve_order(self, order_id: uuid.UUID | None) -> Order | None:
        if order_id is None:
            return None
        if self._order_repo is not None:
            live = self._order_repo._orders.get(order_id)
            if live is not None:
                return live
        return replace(_PLACEHOLDER_ORDER, id=order_id)

    async def create(
        self,
        session: Any,
        *,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        is_paper: bool,
        entry_at: datetime,
        strategy_run_id: uuid.UUID | None,
        legs: list[NewLegSpec],
    ) -> Trade:
        trade_id = uuid.uuid4()
        leg_records = tuple(
            TradeLeg(
                id=uuid.uuid4(),
                instrument_id=spec.instrument_id,
                direction=spec.direction,
                quantity=spec.quantity,
            )
            for spec in legs
        )
        trade = Trade(
            id=trade_id,
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            state=TradeState.PENDING,
            is_paper=is_paper,
            legs=leg_records,
            entry_at=entry_at,
            strategy_run_id=strategy_run_id,
        )
        self._trades[trade_id] = trade
        return trade

    async def set_state(
        self,
        session: Any,
        trade_id: uuid.UUID,
        *,
        new_state: TradeState,
        at: datetime,
        exit_at: datetime | None = None,
        total_realized_pnl: float | None = None,
        close_reason: str | None = None,
    ) -> None:
        trade = self._trades[trade_id]
        self._trades[trade_id] = replace(
            trade,
            state=new_state,
            exit_at=exit_at if exit_at is not None else trade.exit_at,
            total_realized_pnl=(
                total_realized_pnl if total_realized_pnl is not None else trade.total_realized_pnl
            ),
        )
        if close_reason is not None:
            self.close_reasons[trade_id] = close_reason

    async def set_leg_prices(
        self,
        session: Any,
        leg_id: uuid.UUID,
        *,
        entry_price: float | None = None,
        exit_price: float | None = None,
        realized_pnl: float | None = None,
    ) -> None:
        for trade_id, trade in self._trades.items():
            new_legs = []
            changed = False
            for leg in trade.legs:
                if leg.id == leg_id:
                    leg = replace(
                        leg,
                        entry_price=entry_price if entry_price is not None else leg.entry_price,
                        exit_price=exit_price if exit_price is not None else leg.exit_price,
                        realized_pnl=(
                            realized_pnl if realized_pnl is not None else leg.realized_pnl
                        ),
                    )
                    changed = True
                new_legs.append(leg)
            if changed:
                self._trades[trade_id] = replace(trade, legs=tuple(new_legs))
                return

    async def set_entry_order(self, session: Any, leg_id: uuid.UUID, order_id: uuid.UUID) -> None:
        self._entry_order_of[leg_id] = order_id

    async def set_exit_order(self, session: Any, leg_id: uuid.UUID, order_id: uuid.UUID) -> None:
        self._exit_order_of[leg_id] = order_id

    # Test-only helpers
    def add(self, trade: Trade) -> None:
        self._trades[trade.id] = trade


_PLACEHOLDER_ORDER = Order(
    id=uuid.uuid4(),
    state=OrderState.SUBMITTED,
    side=OrderSide.BUY,
    instrument_id=uuid.uuid4(),
    quantity=0.0,
)


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self._orders: dict[uuid.UUID, Order] = {}
        self._leg_of: dict[uuid.UUID, uuid.UUID | None] = {}
        self._trade_of: dict[uuid.UUID, uuid.UUID | None] = {}
        self._exchange_of: dict[uuid.UUID, uuid.UUID] = {}
        self.status_history: list[tuple[uuid.UUID, OrderState, datetime, str | None]] = []
        self._trade_repo: InMemoryTradeRepository | None = None

    def link_trade_repo(self, trade_repo: InMemoryTradeRepository) -> None:
        self._trade_repo = trade_repo

    async def get(self, session: Any, order_id: uuid.UUID) -> Order | None:
        return self._orders.get(order_id)

    async def list_for_exchange(
        self,
        session: Any,
        exchange_id: uuid.UUID,
        *,
        only_non_terminal_trades: bool = True,
    ) -> list[tuple[Order, uuid.UUID, uuid.UUID]]:
        out: list[tuple[Order, uuid.UUID, uuid.UUID]] = []
        for order_id, order in self._orders.items():
            if self._exchange_of.get(order_id) != exchange_id:
                continue
            leg_id = self._leg_of.get(order_id)
            if leg_id is None:
                continue
            trade_id = self._trade_of.get(order_id) or self._lookup_trade_for_leg(leg_id)
            if trade_id is None:
                continue
            if only_non_terminal_trades and self._trade_repo is not None:
                trade = self._trade_repo._trades.get(trade_id)
                if trade is not None and trade.state.is_terminal:
                    continue
            out.append((order, leg_id, trade_id))
        return out

    def _lookup_trade_for_leg(self, leg_id: uuid.UUID) -> uuid.UUID | None:
        if self._trade_repo is None:
            return None
        for trade in self._trade_repo._trades.values():
            for leg in trade.legs:
                if leg.id == leg_id:
                    return trade.id
        return None

    async def create(self, session: Any, spec: NewOrderSpec) -> Order:
        order = Order(
            id=uuid.uuid4(),
            state=OrderState.SUBMITTED,
            side=OrderSide(spec.side),
            instrument_id=spec.instrument_id,
            quantity=spec.quantity,
            price=spec.price,
        )
        self._orders[order.id] = order
        self._leg_of[order.id] = spec.trade_leg_id
        self._exchange_of[order.id] = spec.exchange_id
        return order

    async def record_status(
        self,
        session: Any,
        order_id: uuid.UUID,
        *,
        new_state: OrderState,
        at: datetime,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.status_history.append((order_id, new_state, at, error_message))
        order = self._orders[order_id]
        self._orders[order_id] = replace(order, state=new_state, error_message=error_message)

    async def set_external_id(
        self, session: Any, order_id: uuid.UUID, external_order_id: str
    ) -> None:
        order = self._orders[order_id]
        # Idempotent: the exchange-assigned id is immutable once known. Matches
        # the SqlAlchemy adapter's ``if not order.external_order_id`` guard.
        if order.external_order_id:
            return
        self._orders[order_id] = replace(order, external_order_id=external_order_id)

    async def set_fill(
        self,
        session: Any,
        order_id: uuid.UUID,
        *,
        filled_quantity: float,
        average_fill_price: float | None,
    ) -> None:
        order = self._orders[order_id]
        self._orders[order_id] = replace(
            order,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
        )

    # Test-only helpers
    def add(
        self, order: Order, *, trade_id: uuid.UUID, leg_id: uuid.UUID, exchange_id: uuid.UUID
    ) -> None:
        self._orders[order.id] = order
        self._leg_of[order.id] = leg_id
        self._trade_of[order.id] = trade_id
        self._exchange_of[order.id] = exchange_id


class InMemoryFeedRunRepository(FeedRunRepository):
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, dict] = {}

    async def create(
        self,
        *,
        feed_id: uuid.UUID,
        started_at: datetime,
        snapshot_timestamp: datetime,
    ) -> uuid.UUID:
        run_id = uuid.uuid4()
        self.runs[run_id] = {
            "feed_id": feed_id,
            "snapshot_timestamp": snapshot_timestamp,
            "started_at": started_at,
            "status": "RUNNING",
        }
        return run_id

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None:
        self.runs[run_id]["status"] = "COMPLETED"
        self.runs[run_id]["completed_at"] = at

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None:
        self.runs[run_id]["status"] = "FAILED"
        self.runs[run_id]["completed_at"] = at
        self.runs[run_id]["error_message"] = error_message


class InMemoryStrategyRunRepository(StrategyRunRepository):
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, dict] = {}
        self.links: list[tuple[uuid.UUID, dict[uuid.UUID, uuid.UUID], uuid.UUID]] = []

    async def create(self, *, strategy_id: uuid.UUID, started_at: datetime) -> uuid.UUID:
        run_id = uuid.uuid4()
        self.runs[run_id] = {
            "strategy_id": strategy_id,
            "started_at": started_at,
            "status": "RUNNING",
        }
        return run_id

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None:
        self.runs[run_id]["status"] = "COMPLETED"
        self.runs[run_id]["completed_at"] = at

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None:
        self.runs[run_id]["status"] = "FAILED"
        self.runs[run_id]["completed_at"] = at
        self.runs[run_id]["error_message"] = error_message

    async def link_feed_runs(
        self,
        strategy_run_id: uuid.UUID,
        *,
        feed_run_ids: dict[uuid.UUID, uuid.UUID],
        trigger_feed_id: uuid.UUID,
    ) -> None:
        self.links.append((strategy_run_id, dict(feed_run_ids), trigger_feed_id))


