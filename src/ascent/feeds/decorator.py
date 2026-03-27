"""``@feed`` decorator and ``Feed`` descriptor object."""

from __future__ import annotations

import inspect
import itertools
from typing import TYPE_CHECKING, Any, get_args, get_origin

import pandera.pandas as pa
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

from ascent.feeds.output import FeedOutput
from ascent.feeds.schedule import Schedule

if TYPE_CHECKING:
    from collections.abc import Callable

    from pandera.typing import DataFrame

_feed_id_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_parameters_model(fn: Callable) -> type[BaseModel]:
    """Build a Pydantic model from the function's typed parameters.

    Each parameter becomes a field on the model. ``pydantic.Field`` defaults
    are preserved.  The generated model is named ``{FnName}Parameters``.
    """
    sig = inspect.signature(fn)
    fields: dict[str, Any] = {}

    for name, param in sig.parameters.items():
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        default = param.default if param.default is not inspect.Parameter.empty else ...

        # If the default is a pydantic FieldInfo (from Field()), keep it as-is
        if isinstance(default, FieldInfo):
            fields[name] = (annotation, default)
        else:
            fields[name] = (annotation, default)

    model_name = f"{fn.__name__.replace('_', ' ').title().replace(' ', '')}Parameters"
    return create_model(model_name, **fields)


def _extract_pandera_schema(fn: Callable) -> type[FeedOutput]:
    """Extract the Pandera DataFrameModel from the function's return annotation.

    Expects a return type of ``DataFrame[SomeSchema]`` where ``SomeSchema``
    is a subclass of :class:`FeedOutput`.
    """
    hints = inspect.get_annotations(fn, eval_str=True)
    ret = hints.get("return")
    if ret is None:
        raise TypeError(f"Feed function {fn.__name__!r} must have a return type annotation")

    # Handle DataFrame[Schema] (pandera.typing.DataFrame is generic)
    origin = get_origin(ret)
    if origin is not None:
        args = get_args(ret)
        if args and isinstance(args[0], type) and issubclass(args[0], pa.DataFrameModel):
            schema_cls = args[0]
            if not issubclass(schema_cls, FeedOutput):
                raise TypeError(
                    f"Feed function {fn.__name__!r} return schema {schema_cls.__name__} "
                    f"must be a subclass of FeedOutput"
                )
            return schema_cls

    # Direct FeedOutput subclass (without DataFrame wrapper)
    if isinstance(ret, type) and issubclass(ret, FeedOutput):
        return ret

    raise TypeError(
        f"Feed function {fn.__name__!r} must return DataFrame[FeedOutput subclass], got {ret!r}"
    )


# ---------------------------------------------------------------------------
# Feed object
# ---------------------------------------------------------------------------


class Feed:
    """Descriptor returned by the ``@feed`` decorator.

    Holds the fetch function, schedule/dependency info, Pandera schema,
    and dynamically-built Pydantic parameters model.
    """

    def __init__(
        self,
        fetch_fn: Callable,
        schedule: Schedule | None,
        depends_on: list[Feed] | None,
        display_name: str | None,
        description: str | None,
    ) -> None:
        self._feed_id = next(_feed_id_counter)
        self.fetch_fn = fetch_fn
        self.schedule = schedule
        self.depends_on = depends_on or []
        self.display_name = display_name or fetch_fn.__name__
        self.description = description or fetch_fn.__doc__ or ""
        self._persist_handlers: list[Any] = []
        self._parameters_model = _build_parameters_model(fetch_fn)
        self._schema = _extract_pandera_schema(fetch_fn)

        # Preserve the original function's name for debugging
        self.__name__ = fetch_fn.__name__
        self.__module__ = fetch_fn.__module__
        self.__qualname__ = fetch_fn.__qualname__
        self.__doc__ = fetch_fn.__doc__

    @property
    def ref(self) -> str:
        """Canonical ``module:name`` reference for DB lookup."""
        return f"{self.fetch_fn.__module__}:{self.fetch_fn.__name__}"

    def __call__(self, **kwargs: Any) -> DataFrame:
        """Invoke the feed with the given parameters, validating output."""
        params = self._parameters_model(**kwargs)
        df = self.fetch_fn(**params.model_dump())
        return self._schema.validate(df)

    def parameter_schema(self) -> dict:
        """JSON Schema for this feed's configuration parameters."""
        return self._parameters_model.model_json_schema()

    def data_schema(self) -> dict:
        """JSON Schema for this feed's output DataFrame."""
        return self._schema.to_schema().to_json()

    def output_table(self) -> str:
        """The DB table name this feed's output maps to."""
        return self._schema.Config.name

    def __repr__(self) -> str:
        return f"Feed({self.__name__!r}, table={self.output_table()!r})"


# ---------------------------------------------------------------------------
# Decorator factory
# ---------------------------------------------------------------------------


def feed(
    *,
    schedule: Schedule | None = None,
    depends_on: list[Feed] | None = None,
    display_name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], Feed]:
    """Decorator that registers a function as an Ascent data feed.

    A feed with ``schedule`` is timer-driven. A feed with ``depends_on`` is
    triggered by parent feeds. A feed with neither is assumed to be
    **external** — its data is published via the Ascent API.

    The decorated function must return ``DataFrame[FeedOutput subclass]``.
    Parameters are auto-extracted as a Pydantic model for JSON Schema / UI.

    Args:
        schedule: When to fire (interval + offset + optional anchor).
        depends_on: Parent feeds that trigger this feed (AND logic).
        display_name: Human-readable name shown in the UI.
        description: Long description shown in the UI.
    """
    if schedule is not None and depends_on:
        raise ValueError("A feed cannot have both 'schedule' and 'depends_on'")

    def decorator(fn: Callable) -> Feed:
        return Feed(
            fetch_fn=fn,
            schedule=schedule,
            depends_on=depends_on,
            display_name=display_name,
            description=description,
        )

    return decorator
