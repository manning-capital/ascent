"""Abstract base class for all Ascent trading strategies.

Every strategy deployed to Ascent must subclass ``Strategy`` and define an
inner ``Parameters`` class (a Pydantic BaseModel) that describes the knobs
the strategy exposes.  Ascent uses ``Parameters.model_json_schema()`` to
generate a JSON Schema that the UI renders as a typed form — so users never
have to edit raw JSON.

Example
-------
::

    from pydantic import BaseModel, Field
    from ascent.strategies import Strategy
    from feeds.market import MarketData

    class PairsStrategy(Strategy):
        class Parameters(BaseModel):
            lookback: int = Field(60, description="Rolling window size in bars")
            entry_z: float = Field(2.0, description="Z-score threshold to enter")
            exit_z: float = Field(0.5, description="Z-score threshold to exit")

        feeds = [MarketData]

        def evaluate(self) -> None:
            ctx = self.get_context()
            prices = ctx.get(MarketData)
            ...

    if __name__ == "__main__":
        PairsStrategy.run()
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from ascent.engine.context import StrategyContext
    from ascent.engine.trade_router import TradeRouter
    from ascent.feeds.base import Feed


class Strategy(ABC):
    """Base class that every Ascent trading strategy must inherit from.

    Subclasses **must** override the inner ``Parameters`` class with a
    Pydantic model describing the strategy's configuration.  The schema
    is extracted at deploy time and stored alongside the model record so
    the UI can render a proper form.
    """

    class Parameters(BaseModel):
        """Override this in your strategy to define typed parameters.

        The default is an empty model (no parameters).  Subclasses replace
        this entirely::

            class MyStrategy(Strategy):
                class Parameters(BaseModel):
                    threshold: float = 1.5
        """

    #: Populated by __init__ with a validated Parameters instance.
    parameters: Parameters

    #: Feeds this strategy depends on.  Each entry can be a feed name
    #: (string), a UUID, or a Feed subclass.  The engine resolves names
    #: and UUIDs at deploy time and subscribes to their Redis channels.
    feeds: ClassVar[list[str | type[Feed]] | None] = None

    #: Human-readable name shown in the UI.  Override in subclasses or
    #: leave ``None`` to use the class name.
    display_name: ClassVar[str | None] = None

    #: Optional long description shown in the UI.
    description: ClassVar[str | None] = None

    #: Portfolio name or UUID.  Resolved to a UUID at deploy time.
    portfolio: ClassVar[str | None] = None

    #: Exchanges this strategy can use for order execution.  Each entry
    #: can be an exchange name (string) or a UUID.
    exchanges: ClassVar[list[str] | None] = None

    def __init__(self, parameters: Parameters | dict | None = None) -> None:
        if parameters is None:
            parameters = {}
        if isinstance(parameters, dict):
            parameters = self.__class__.Parameters.model_validate(parameters)
        self.parameters = parameters
        self._trade_router: TradeRouter | None = None

    # ------------------------------------------------------------------
    # Core — called by the execution engine on each tick
    # ------------------------------------------------------------------

    @abstractmethod
    def evaluate(self) -> None:
        """Called on each execution tick.  Must be implemented by subclasses."""

    # ------------------------------------------------------------------
    # Runtime accessors (thin wrappers around contextvars)
    # ------------------------------------------------------------------

    def get_context(self) -> StrategyContext:
        """Get the current strategy evaluation context."""
        from ascent.engine.context import _current_context

        try:
            return _current_context.get()
        except LookupError:
            raise RuntimeError("get_context() called outside of a strategy evaluation.") from None

    def get_logger(self) -> logging.Logger:
        """Get the current run-scoped logger."""
        from ascent.engine.context import _current_logger

        try:
            return _current_logger.get()
        except LookupError:
            return logging.getLogger(f"ascent.strategies.{type(self).__name__}")

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    def _ensure_router(self) -> TradeRouter:
        if self._trade_router is None:
            raise RuntimeError(
                "No exchange is configured for this strategy. "
                "Declare 'exchanges = [\"EXCHANGE_NAME\"]' on your strategy class "
                "and make sure the exchange is deployed and active."
            )
        return self._trade_router

    def open_trade(
        self,
        id: uuid.UUID,
        direction: str,
        quantity: float,
        *,
        scope: Literal["instrument", "composite"] = "instrument",
        price: float | None = None,
        order_type: str = "MARKET",
    ) -> dict:
        """Open a new trade on an instrument or composite.

        Args:
            id: The UUID of the instrument or composite.
            direction: ``LONG`` or ``SHORT``.
            quantity: Number of units per leg.
            scope: ``"instrument"`` for a single-leg trade, or
                ``"composite"`` for a multi-leg trade (one leg per
                member — first member follows *direction*, remaining
                members take the opposite side).
            price: Limit price. None for market orders.
            order_type: ``MARKET`` or ``LIMIT``.

        Returns:
            Dict with ``trade_id``, ``status`` (OPEN/OPENING/ERROR),
            and ``legs`` (list of per-leg details).
        """
        router = self._ensure_router()
        side = "BUY" if direction == "LONG" else "SELL"
        return router.submit(
            side=side,
            target_id=id,
            scope=scope,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    def close_trade(
        self,
        trade_id: str | uuid.UUID,
        *,
        price: float | None = None,
        close_reason: str = "MODEL_SIGNAL",
    ) -> dict:
        """Close an open trade by submitting exit orders for all legs.

        Args:
            trade_id: The UUID of the trade to close.
            price: Exit price (used for all legs). None for market.
            close_reason: ``MODEL_SIGNAL``, ``STOP_LOSS``, ``TAKE_PROFIT``, etc.

        Returns:
            Dict with ``trade_id``, ``status`` (CLOSED/CLOSING/ERROR),
            and ``total_pnl``.
        """
        router = self._ensure_router()
        return router.close(
            trade_id=uuid.UUID(str(trade_id)),
            price=price,
            close_reason=close_reason,
        )

    def get_open_trades(self) -> list[dict]:
        """Return all OPEN trades for this strategy.

        Returns:
            List of dicts with ``trade_id``, ``entry_at``, ``is_paper``.
        """
        router = self._ensure_router()
        return router.get_open_trades()

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @classmethod
    def parameter_schema(cls) -> dict:
        """Return the JSON Schema for this strategy's Parameters model.

        This is what gets stored in the database and served to the UI.
        """
        return cls.Parameters.model_json_schema()

    @classmethod
    def ref(cls) -> str:
        """Canonical reference for DB lookup.  Uses the name."""
        return cls.get_name()

    @classmethod
    def get_name(cls) -> str:
        """Return the unique name (``UPPER_SNAKE_CASE``).

        Derives from the class name by inserting underscores before
        uppercase letters and uppercasing
        (e.g. ``TimingStrategy`` -> ``TIMING_STRATEGY``).
        """
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", cls.__name__).upper()

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name.

        If ``display_name`` is not set, derives it from the class name
        by inserting spaces before each uppercase letter
        (e.g. ``TimingStrategy`` -> ``Timing Strategy``).
        """
        if cls.display_name:
            return cls.display_name
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cls.__name__)

    @classmethod
    def feed_refs(cls) -> list[str]:
        """Return ``module:ClassName`` references for all declared feeds."""
        if cls.feeds is None:
            return []
        return [f.ref() for f in cls.feeds]

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    @classmethod
    def run(
        cls,
        *,
        database_url: str | None = None,
        redis_url: str | None = None,
        log_level: str = "INFO",
    ) -> None:
        """Auto-deploy and run this strategy as a long-running process.

        Registers (or updates) the strategy in the database, then starts
        the engine consumer loop.  Blocks until SIGINT/SIGTERM.
        """
        from ascent.engine.runner import Runner

        runner = Runner(
            database_url=database_url,
            redis_url=redis_url,
            log_level=log_level,
        )
        runner.add(cls)
        runner.run()
