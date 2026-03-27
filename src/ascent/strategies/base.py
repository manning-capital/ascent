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

    class PairsStrategy(Strategy):
        class Parameters(BaseModel):
            lookback: int = Field(60, description="Rolling window size in bars")
            entry_z: float = Field(2.0, description="Z-score threshold to enter")
            exit_z: float = Field(0.5, description="Z-score threshold to exit")

        def start(self) -> None:
            ...

        def evaluate(self) -> None:
            ...

        def stop(self) -> None:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


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
    # Lifecycle hooks — called by the execution engine
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Called once when the strategy is initialised (before first evaluate)."""

    @abstractmethod
    def evaluate(self) -> None:
        """Called on each execution tick.  Must be implemented by subclasses."""

    def stop(self) -> None:
        """Called once when the strategy is shut down (after last evaluate)."""

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
    def get_display_name(cls) -> str:
        """Return the display name, falling back to the class name."""
        return cls.display_name or cls.__name__
