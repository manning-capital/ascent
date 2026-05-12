"""Core trading domain — pure value types with no I/O or ORM coupling.

These types are what the state machine operates on. Adapters translate
between these types and persistence layers (SQLAlchemy, Redis, exchange APIs).
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PositionType(str, enum.Enum):
    """Direction or holding type of a position.

    Today only ``LONG`` and ``SHORT`` are valid; future values
    (``STAKED``, ``BORROWED``, ``PROVIDED_LIQUIDITY``) extend the enum
    without schema change. ``TradeLeg.direction`` is always ``LONG`` or
    ``SHORT`` — non-directional position types only apply to holdings.
    """

    LONG = "LONG"
    SHORT = "SHORT"


class OrderState(str, enum.Enum):
    """Order lifecycle. Terminal: FILLED, CANCELLED, REJECTED."""

    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

    @property
    def is_terminal(self) -> bool:
        return self in _ORDER_TERMINAL

    @property
    def is_active(self) -> bool:
        return self in _ORDER_ACTIVE


_ORDER_TERMINAL = frozenset({OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED})
_ORDER_ACTIVE = frozenset({OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED})


class TradeState(str, enum.Enum):
    """Trade lifecycle. Terminal: CLOSED, CANCELLED, REJECTED."""

    PENDING = "PENDING"
    OPENING = "OPENING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

    @property
    def is_terminal(self) -> bool:
        return self in _TRADE_TERMINAL


_TRADE_TERMINAL = frozenset({TradeState.CLOSED, TradeState.CANCELLED, TradeState.REJECTED})


@dataclass(frozen=True)
class Order:
    id: uuid.UUID
    state: OrderState
    side: OrderSide
    instrument_id: uuid.UUID
    quantity: float
    price: float | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    external_order_id: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class TradeLeg:
    id: uuid.UUID
    instrument_id: uuid.UUID
    direction: PositionType
    quantity: float
    entry_order: Order | None = None
    exit_order: Order | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None
    from_asset_symbol: str | None = None
    to_asset_symbol: str | None = None
    exchange_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Trade:
    id: uuid.UUID
    strategy_id: uuid.UUID
    state: TradeState
    is_paper: bool
    legs: tuple[TradeLeg, ...]
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    total_realized_pnl: float | None = None
    strategy_run_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None


@dataclass(frozen=True)
class FillEvent:
    """A fill update from an exchange, scoped to a single order."""

    order_id: uuid.UUID
    state: OrderState
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    external_order_id: str | None = None
    error_message: str | None = None
