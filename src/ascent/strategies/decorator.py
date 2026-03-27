"""``@strategy`` decorator and ``StrategyDef`` descriptor object."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from ascent.feeds.decorator import Feed


def _build_parameters_model(fn: Callable) -> type[BaseModel]:
    """Build a Pydantic model from the function's typed parameters.

    Each parameter becomes a field on the model.  ``pydantic.Field`` defaults
    are preserved.
    """
    sig = inspect.signature(fn)
    fields: dict[str, Any] = {}

    for name, param in sig.parameters.items():
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        default = param.default if param.default is not inspect.Parameter.empty else ...

        if isinstance(default, FieldInfo):
            fields[name] = (annotation, default)
        else:
            fields[name] = (annotation, default)

    model_name = f"{fn.__name__.replace('_', ' ').title().replace(' ', '')}Parameters"
    return create_model(model_name, **fields)


class StrategyDef:
    """Descriptor returned by the ``@strategy`` decorator.

    Holds the evaluate function, declared feed dependencies, and a
    dynamically-built Pydantic parameters model.
    """

    def __init__(
        self,
        fn: Callable,
        feeds: list[Feed],
        display_name: str | None,
        description: str | None,
    ) -> None:
        self.evaluate_fn = fn
        self.feeds = feeds
        self.display_name = display_name or fn.__name__
        self.description = description or fn.__doc__ or ""
        self._parameters_model = _build_parameters_model(fn)

        self.__name__ = fn.__name__
        self.__module__ = fn.__module__
        self.__qualname__ = fn.__qualname__
        self.__doc__ = fn.__doc__

    def __call__(self, **kwargs: Any) -> Any:
        """Invoke the strategy evaluate function with validated parameters."""
        params = self._parameters_model(**kwargs)
        return self.evaluate_fn(**params.model_dump())

    def parameter_schema(self) -> dict:
        """JSON Schema for this strategy's configuration parameters."""
        return self._parameters_model.model_json_schema()

    def feed_refs(self) -> list[str]:
        """Return ``module:name`` references for all declared feeds."""
        return [f.ref for f in self.feeds]

    def __repr__(self) -> str:
        feed_names = [f.__name__ for f in self.feeds]
        return f"StrategyDef({self.__name__!r}, feeds={feed_names!r})"


def strategy(
    *,
    feeds: list[Feed],
    display_name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], StrategyDef]:
    """Decorator that registers a function as an Ascent trading strategy.

    The ``feeds`` parameter explicitly declares which feeds the strategy
    consumes.  The engine uses this for Redis pub/sub channel subscription, and the
    deploy CLI auto-creates ``StrategyFeed`` records.

    Function parameters are auto-extracted as a Pydantic model for
    JSON Schema / UI rendering.

    Args:
        feeds: Feed objects this strategy depends on.
        display_name: Human-readable name shown in the UI.
        description: Long description shown in the UI.
    """

    def decorator(fn: Callable) -> StrategyDef:
        return StrategyDef(
            fn=fn,
            feeds=feeds,
            display_name=display_name,
            description=description,
        )

    return decorator
