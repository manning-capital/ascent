"""Runtime context for strategies and feeds.

Provides ``get_context()``, ``get_logger()``, ``get_feed()``, and ``get_partition()``
— contextvars-based accessors that the engine sets before invoking decorated functions.
"""

from __future__ import annotations

import contextvars
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel

if TYPE_CHECKING:
    from ascent.feeds.decorator import Feed


# ---------------------------------------------------------------------------
# Partition info model
# ---------------------------------------------------------------------------


class PartitionInfo(BaseModel):
    """Information about the current partition being executed."""

    key: datetime
    """The partition key (boundary time)."""

    window_start: datetime
    """Start of the time window (inclusive)."""

    window_end: datetime
    """End of the time window (exclusive)."""


# ---------------------------------------------------------------------------
# Context variables — set by the engine, read by user code
# ---------------------------------------------------------------------------

_current_context: contextvars.ContextVar[StrategyContext] = contextvars.ContextVar("ascent_context")
_current_logger: contextvars.ContextVar[logging.Logger] = contextvars.ContextVar("ascent_logger")
_current_feeds: contextvars.ContextVar[dict[int, pd.DataFrame]] = contextvars.ContextVar(
    "ascent_feeds"
)
_current_partition: contextvars.ContextVar[PartitionInfo] = contextvars.ContextVar(
    "ascent_partition"
)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------


def get_context() -> StrategyContext:
    """Get the current strategy context. Call from within a ``@strategy`` function."""
    try:
        return _current_context.get()
    except LookupError:
        raise RuntimeError(
            "get_context() called outside of a strategy evaluation. "
            "This function can only be called inside a @strategy-decorated function."
        ) from None


def get_logger() -> logging.Logger:
    """Get the current run-scoped logger. Call from within ``@strategy`` or ``@feed`` functions."""
    try:
        return _current_logger.get()
    except LookupError:
        raise RuntimeError(
            "get_logger() called outside of a run context. "
            "This function can only be called inside a @strategy or @feed-decorated function."
        ) from None


def get_feed(feed: Feed) -> pd.DataFrame:
    """Get a parent feed's latest data inside a ``@feed(depends_on=...)`` function.

    Args:
        feed: The parent Feed object to retrieve data for.

    Returns:
        The parent feed's latest output as a DataFrame.
    """
    try:
        feeds = _current_feeds.get()
    except LookupError:
        raise RuntimeError(
            "get_feed() called outside of a triggered feed context. "
            "This function can only be called inside a @feed(depends_on=...) function."
        ) from None
    if feed._feed_id not in feeds:
        raise KeyError(
            f"Feed {feed.__name__!r} (id={feed._feed_id}) not found in current feeds context. "
            f"Make sure it is listed in depends_on."
        )
    return feeds[feed._feed_id]


def get_partition() -> PartitionInfo:
    """Get the current partition window. Call from within a ``@feed`` function.

    Returns:
        A :class:`PartitionInfo` with ``key``, ``window_start``, and ``window_end``.
    """
    try:
        return _current_partition.get()
    except LookupError:
        raise RuntimeError(
            "get_partition() called outside of a feed run context. "
            "This function can only be called inside a @feed-decorated function "
            "during engine execution."
        ) from None


# ---------------------------------------------------------------------------
# StrategyContext
# ---------------------------------------------------------------------------


class StrategyContext:
    """Vectorized evaluation context retrieved via ``get_context()`` inside ``@strategy`` functions.

    All data is DataFrame-based for vectorized evaluation across instruments.
    No Python ``for`` loops — strategies use pandas/numpy for C-level speed.

    Attributes:
        instruments: One row per instrument. Index = ``instrument_id``. Columns:
            ``state`` ('waiting' | 'in_trade'), ``trade_id`` (int | None).
        composites: One row per composite. Index = ``composite_id``. Columns:
            ``state`` ('waiting' | 'in_trade'), ``trade_id`` (int | None),
            ``member_instrument_ids`` (list[int]).
    """

    def __init__(
        self,
        instruments: pd.DataFrame,
        composites: pd.DataFrame,
        feed_frames: dict[int, pd.DataFrame],
    ) -> None:
        self.instruments = instruments
        self.composites = composites
        self._feed_frames = feed_frames

    def get(self, feed: Feed) -> pd.DataFrame:
        """Get feed data as a DataFrame for ALL instruments.

        Returns a DataFrame with columns:
          - ``instrument_id``: int (matches ``instruments.index``)
          - ``timestamp``: datetime
          - ``{attribute_name}``: float (one column per attribute, pivoted from EAV rows)

        The engine pre-joins attribute IDs → names and pivots from EAV format
        into a wide DataFrame.  Strategies never deal with ``attribute_id`` integers.
        """
        if feed._feed_id not in self._feed_frames:
            raise KeyError(
                f"Feed {feed.__name__!r} (id={feed._feed_id}) not found in strategy context. "
                f"Make sure it is listed in @strategy(feeds=[...])."
            )
        return self._feed_frames[feed._feed_id]

    def __repr__(self) -> str:
        n_instruments = len(self.instruments)
        n_composites = len(self.composites)
        n_feeds = len(self._feed_frames)
        return f"StrategyContext(instruments={n_instruments}, composites={n_composites}, feeds={n_feeds})"
