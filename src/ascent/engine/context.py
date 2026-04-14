"""Runtime context for strategies and feeds.

Provides ``get_logger()``, ``get_feed()``, and ``get_partition()``
— contextvars-based accessors that the engine sets before invoking user code.
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

_current_logger: contextvars.ContextVar[logging.Logger] = contextvars.ContextVar("ascent_logger")
_current_feeds: contextvars.ContextVar[dict[str, pd.DataFrame]] = contextvars.ContextVar(
    "ascent_feeds"
)
_current_partition: contextvars.ContextVar[PartitionInfo] = contextvars.ContextVar(
    "ascent_partition"
)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------


def get_logger() -> logging.Logger:
    """Get the current run-scoped logger. Call from within a strategy or feed function."""
    try:
        return _current_logger.get()
    except LookupError:
        raise RuntimeError(
            "get_logger() called outside of a run context. "
            "This function can only be called inside a strategy evaluate() or feed fetch()."
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
    """Get the current partition window. Call from within a feed function.

    Returns:
        A :class:`PartitionInfo` with ``key``, ``window_start``, and ``window_end``.
    """
    try:
        return _current_partition.get()
    except LookupError:
        raise RuntimeError(
            "get_partition() called outside of a feed run context. "
            "This function can only be called inside a feed during engine execution."
        ) from None
