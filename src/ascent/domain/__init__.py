"""Ascent domain layer — pure value types and deterministic state machines.

This layer has no I/O, no ORM coupling, no framework dependencies. Everything
here is a pure Python value type or a pure function. Adapter code maps these
types to/from SQLAlchemy models, Redis payloads, exchange APIs, etc.
"""

from ascent.domain.context import (
    Attribute,
    Context,
    ContextSource,
    Period,
    RunContext,
    RuntimeSource,
)
from ascent.domain.feed import FeedTick
from ascent.domain.state_machine import (
    LegUpdate,
    OrderUpdate,
    TradeTransition,
    apply_fill,
    opening_from_orders,
)
from ascent.domain.trade import (
    Direction,
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    OrderType,
    Trade,
    TradeLeg,
    TradeState,
)

__all__ = [
    "Attribute",
    "Context",
    "ContextSource",
    "Direction",
    "FeedTick",
    "FillEvent",
    "LegUpdate",
    "Order",
    "OrderSide",
    "OrderState",
    "OrderType",
    "OrderUpdate",
    "Period",
    "RunContext",
    "RuntimeSource",
    "Trade",
    "TradeLeg",
    "TradeState",
    "TradeTransition",
    "apply_fill",
    "opening_from_orders",
]
