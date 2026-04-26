"""Pydantic response schemas for the context-reconstruction API.

The response carries:
- ``context`` — the same ``ascent.domain.Context`` shape that's persisted on
  ``FeedRun.context`` and inherited by the runtime ``RunContext``. The UI
  view stays in sync with the engine view because it's literally the same
  Pydantic model.
- ``series`` — the resolved time series the spec describes, ready to render.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ascent.domain import Attribute, Context, Period


class SeriesPoint(BaseModel):
    t: datetime
    v: float


class SeriesScopeRef(BaseModel):
    type: Literal["instrument", "composite"]
    id: uuid.UUID
    name: str | None = None
    display_name: str | None = None


class ContextSeries(BaseModel):
    """One time-series within a reconstructed context.

    The ``name`` follows the canonical
    ``{ATTRIBUTE_NAME}[{PERIOD_NAME}]@{scope.type}:{scope.name}`` rule —
    collision-proof across instrument vs. composite and across periods.
    """

    name: str
    display_name: str
    attribute: Attribute
    period: Period | None = None
    scope: SeriesScopeRef
    source_table: Literal[
        "instrument_attribute",
        "instrument_period_attribute",
        "composite_attribute",
        "composite_period_attribute",
    ]
    source_feed_run_ids: list[uuid.UUID]
    points: list[SeriesPoint]


class TradeViewSchema(BaseModel):
    """Per-strategy trade-detail chart configuration.

    Mirrors the persisted ``Strategy.trade_view`` JSONB. The trade-detail UI
    uses ``series`` to seed default series selection (by attribute name) and
    overlays vertical reference lines at the trade's entry/exit timestamps
    when ``show_trade_markers`` is true.
    """

    series: list[str] = []
    series_labels: dict[str, str] = {}
    show_trade_markers: bool = True


class ContextResponse(BaseModel):
    """Reconstructed view of what a run (or scope) cared about.

    The ``context`` field is the literal Pydantic shape the engine wrote
    to ``FeedRun.context``; the ``series`` field is the resolved data.
    """

    context: Context
    series: list[ContextSeries]
    trade_view: TradeViewSchema | None = None
