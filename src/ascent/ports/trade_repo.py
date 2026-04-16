"""Persistence ports for trades, orders, feed runs, strategy runs, and partitions.

The repositories return domain types (``ascent.domain``), not SQLAlchemy
models. The use cases work exclusively with domain types.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from ascent.domain import (
    Direction,
    Order,
    OrderState,
    OrderType,
    Trade,
    TradeLeg,
    TradeState,
)


@runtime_checkable
class TradeRepository(Protocol):
    async def get(self, trade_id: uuid.UUID) -> Trade | None: ...

    async def list_non_terminal_for_strategy(self, strategy_id: uuid.UUID) -> list[Trade]: ...

    async def list_open_for_strategy(self, strategy_id: uuid.UUID) -> list[Trade]: ...

    async def create(
        self,
        *,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        is_paper: bool,
        entry_at: datetime,
        strategy_run_id: uuid.UUID | None,
        legs: list[NewLegSpec],
    ) -> Trade: ...

    async def set_state(
        self,
        trade_id: uuid.UUID,
        *,
        new_state: TradeState,
        at: datetime,
        exit_at: datetime | None = None,
        total_realized_pnl: float | None = None,
        close_reason: str | None = None,
    ) -> None: ...

    async def set_leg_prices(
        self,
        leg_id: uuid.UUID,
        *,
        entry_price: float | None = None,
        exit_price: float | None = None,
        realized_pnl: float | None = None,
    ) -> None: ...

    async def set_entry_order(self, leg_id: uuid.UUID, order_id: uuid.UUID) -> None: ...

    async def set_exit_order(self, leg_id: uuid.UUID, order_id: uuid.UUID) -> None: ...


@runtime_checkable
class OrderRepository(Protocol):
    async def get(self, order_id: uuid.UUID) -> Order | None: ...

    async def list_for_exchange(
        self, exchange_id: uuid.UUID, *, only_non_terminal_trades: bool = True
    ) -> list[tuple[Order, uuid.UUID, uuid.UUID]]:
        """Returns tuples of (order, leg_id, trade_id) for reconciliation."""
        ...

    async def create(self, spec: NewOrderSpec) -> Order: ...

    async def record_status(
        self,
        order_id: uuid.UUID,
        *,
        new_state: OrderState,
        at: datetime,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> None: ...

    async def set_external_id(self, order_id: uuid.UUID, external_order_id: str) -> None: ...

    async def set_fill(
        self,
        order_id: uuid.UUID,
        *,
        filled_quantity: float,
        average_fill_price: float | None,
    ) -> None: ...


@runtime_checkable
class FeedRunRepository(Protocol):
    async def create(
        self,
        *,
        feed_id: uuid.UUID,
        started_at: datetime,
        partition_id: uuid.UUID | None = None,
    ) -> uuid.UUID: ...

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None: ...

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None: ...


@runtime_checkable
class StrategyRunRepository(Protocol):
    async def create(self, *, strategy_id: uuid.UUID, started_at: datetime) -> uuid.UUID: ...

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None: ...

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None: ...

    async def link_feed_runs(
        self,
        strategy_run_id: uuid.UUID,
        *,
        feed_run_ids: dict[uuid.UUID, uuid.UUID],
        trigger_feed_id: uuid.UUID,
    ) -> None: ...


@runtime_checkable
class PartitionRepository(Protocol):
    async def find_or_create(
        self,
        *,
        feed_id: uuid.UUID,
        key: datetime,
        window_start: datetime,
        window_end: datetime,
    ) -> uuid.UUID: ...

    async def set_status(self, partition_id: uuid.UUID, status: str) -> None: ...


# ---------------------------------------------------------------------------
# Repository request DTOs — keep repo signatures sane
# ---------------------------------------------------------------------------


from dataclasses import dataclass  # noqa: E402


@dataclass(frozen=True)
class NewLegSpec:
    instrument_id: uuid.UUID
    direction: Direction
    quantity: float
    expected_entry_price: float | None
    exchange_id: uuid.UUID


@dataclass(frozen=True)
class NewOrderSpec:
    timestamp: datetime
    order_type: OrderType
    side: str
    quantity: float
    price: float
    exchange_id: uuid.UUID
    portfolio_id: uuid.UUID
    instrument_id: uuid.UUID
    trade_leg_id: uuid.UUID | None


# Re-exports needed for type-checking of repository TYPE_CHECKING blocks.
_ = (Direction, Order, OrderState, OrderType, Trade, TradeLeg, TradeState)
