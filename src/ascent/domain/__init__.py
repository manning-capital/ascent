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
from ascent.domain.holdings import StrategyAssetHolding
from ascent.domain.state_machine import (
    LegUpdate,
    OrderUpdate,
    TradeTransition,
    apply_fill,
    opening_from_orders,
)
from ascent.domain.trade import (
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    OrderType,
    PositionType,
    Trade,
    TradeLeg,
    TradeState,
)
from ascent.domain.trade_view import (
    ColorToken,
    Plot,
    PlotSeries,
    SeriesStyle,
    TradeView,
)

__all__ = [
    "Attribute",
    "ColorToken",
    "Context",
    "ContextSource",
    "PositionType",
    "FeedTick",
    "FillEvent",
    "LegUpdate",
    "Order",
    "OrderSide",
    "OrderState",
    "OrderType",
    "OrderUpdate",
    "Period",
    "Plot",
    "PlotSeries",
    "RunContext",
    "RuntimeSource",
    "SeriesStyle",
    "StrategyAssetHolding",
    "Trade",
    "TradeLeg",
    "TradeState",
    "TradeTransition",
    "TradeView",
    "apply_fill",
    "opening_from_orders",
]
