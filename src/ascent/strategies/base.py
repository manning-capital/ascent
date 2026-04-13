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
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from ascent.engine.context import StrategyContext
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

    #: Feed classes this strategy depends on.  The engine subscribes
    #: to these feeds' Redis pub/sub channels.
    feeds: ClassVar[list[type[Feed]] | None] = None

    #: Human-readable name shown in the UI.  Override in subclasses or
    #: leave ``None`` to use the class name.
    display_name: ClassVar[str | None] = None

    #: Optional long description shown in the UI.
    description: ClassVar[str | None] = None

    def __init__(self, parameters: Parameters | dict | None = None) -> None:
        if parameters is None:
            parameters = {}
        if isinstance(parameters, dict):
            parameters = self.__class__.Parameters.model_validate(parameters)
        self.parameters = parameters

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
        """Canonical ``module:ClassName`` reference for DB lookup."""
        return f"{cls.__module__}:{cls.__name__}"

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name, falling back to the class name."""
        return cls.display_name or cls.__name__

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
