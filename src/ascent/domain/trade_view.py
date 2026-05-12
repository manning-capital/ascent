"""Per-strategy trade-detail chart configuration.

Single source of truth shared by ``ascent.strategies.base.Strategy.trade_view``
(the strategy-author class attribute) and ``ascent.server.schemas.context``
(the wire shape returned to the UI). Both sides import from here so the
serialized JSONB row, the API response, and the strategy-author surface can
never drift apart.

A ``TradeView`` is captured at strategy deploy time and persisted as JSONB on
the strategy DB row. The trade-detail UI reads it back to render one or more
named plots organized as tabs, each with curated series, per-series styling,
optional trade-lifecycle overlays, and progressive-line animation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator

#: Closed set of PrimeNG semantic tokens. Resolved at render time to CSS
#: variables (``--p-primary-color``, etc.) so charts re-theme automatically
#: when the user toggles light/dark or swaps PrimeNG presets. No raw CSS
#: strings — keeps the schema theme-portable by construction.
ColorToken = Literal[
    "primary",
    "secondary",
    "success",
    "info",
    "warning",
    "danger",
    "neutral",
    "muted",
]


class SeriesStyle(BaseModel):
    """Visual styling for a single series within a plot."""

    color: ColorToken | None = None
    line_style: Literal["solid", "dashed", "dotted"] = "solid"
    line_width: float = 2.0
    opacity: float = 1.0
    point_radius: float = 0.0
    point_style: Literal["circle", "cross", "triangle", "rect", "rectRot"] = "circle"
    fill: bool = False


class PlotSeries(BaseModel):
    """One series rendered on a plot.

    ``name`` matches ``ContextSeries.attribute.name`` from the context API
    response. When multiple ``ContextSeries`` share that attribute (e.g. one
    per composite scope), they all render under this configuration as
    separate datasets, disambiguated by the auto-color hash.
    """

    name: str
    label: str | None = None
    style: SeriesStyle = SeriesStyle()


class Plot(BaseModel):
    """One chart inside a TradeView. Each plot becomes a tab in the UI."""

    id: str
    title: str
    series: list[PlotSeries]
    main_series_name: str | None = None
    show_legend: bool = True
    legend_position: Literal["top", "bottom", "left", "right"] = "top"
    y_axis_label: str | None = None
    plot_type: Literal["line"] = "line"


class TradeView(BaseModel):
    """Strategy-curated trade-detail chart configuration."""

    plots: list[Plot] = []
    show_trade_markers: bool = True
    show_trade_status_overlay: bool = True

    @model_validator(mode="before")
    @classmethod
    def _ignore_legacy_shape(cls, data: Any) -> Any:
        if isinstance(data, dict) and "series" in data and "plots" not in data:
            return {"show_trade_markers": data.get("show_trade_markers", True)}
        return data
