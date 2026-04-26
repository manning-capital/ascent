"""Context types — the structural pointer and the runtime view.

`Context` is the small, persistable, transportable pointer: which tables,
which scope types, which attributes a run cared about, and when. It is what
gets stored on `FeedRun.context` JSONB and what the API returns.

`RunContext` extends it with the resolved data (`df`) and the runtime
identities (`runtime_sources.scope_ids`). It is what `Feed.fetch(ctx)` and
`Strategy.evaluate(ctx)` receive. It never crosses a process boundary.

`Period` and `Attribute` mirror the `period` and `attribute` DB entities as
domain value-objects, carrying canonical id + name (for joins and UI).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class Period(BaseModel):
    """Mirror of the `period` DB entity as a domain value object."""

    id: uuid.UUID
    name: str
    duration_nanoseconds: int | None = None


class Attribute(BaseModel):
    """Mirror of the `attribute` DB entity as a domain value object.

    Open extensibility: future dimensions (aggregation, transformation,
    units) can be added as new optional fields without breaking the wire
    shape.
    """

    id: uuid.UUID
    name: str
    display_name: str | None = None
    period: Period | None = None


class ContextSource(BaseModel):
    """One slice of the data plane: a table + scope type + attributes.

    Structural only — no scope identities. Identities live on `RuntimeSource`.
    """

    table: Literal[
        "instrument_attribute",
        "instrument_period_attribute",
        "composite_attribute",
        "composite_period_attribute",
    ]
    scope_type: Literal["instrument", "composite"]
    attributes: list[Attribute]


class RuntimeSource(ContextSource):
    """`ContextSource` + the specific `scope_ids` in play at runtime.

    Resolved at run start from the bitemporal scope tables as-of
    `RunContext.snapshot_timestamp`. Never persisted.
    """

    scope_ids: list[uuid.UUID]


class Context(BaseModel):
    """The structural-plus-temporal pointer.

    Persisted on `FeedRun.context` JSONB. Returned by `/api/.../context`
    endpoints. Inherited by `RunContext` so `ctx.sources` and
    `ctx.snapshot_timestamp` are first-class on the runtime object too.
    """

    snapshot_timestamp: datetime
    sources: list[ContextSource]


class RunContext(Context):
    """Runtime view: `Context` + identities + resolved data.

    Inherits `snapshot_timestamp` and `sources`. Adds the in-memory
    DataFrame and the `runtime_sources` (scope ids per source). Never
    serialized; never persisted; never crosses a process boundary.

    `Strategy.evaluate(ctx)` and `Feed.fetch(ctx)` receive this.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    df: pd.DataFrame
    runtime_sources: list[RuntimeSource]
    universe: frozenset[str] = Field(default_factory=frozenset)
    open_only: frozenset[str] = Field(default_factory=frozenset)

    def to_context(self) -> Context:
        """Project to the persistable/serializable `Context` shape.

        Drops df, runtime_sources, universe, open_only. Keeps the
        structural sources and the snapshot timestamp — exactly what the
        JSONB column and the API response carry.
        """
        return Context(
            snapshot_timestamp=self.snapshot_timestamp,
            sources=self.sources,
        )
