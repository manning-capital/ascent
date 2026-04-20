"""Runtime context for strategies and feeds.

Provides ``get_logger()``, ``get_feed()``, and ``get_snapshot()``
— contextvars-based accessors that the engine sets before invoking user code.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ascent.feeds.decorator import Feed


# ---------------------------------------------------------------------------
# Context variables — set by the engine, read by user code
# ---------------------------------------------------------------------------

_current_logger: contextvars.ContextVar[logging.Logger] = contextvars.ContextVar("ascent_logger")
_current_feeds: contextvars.ContextVar[dict[str, pd.DataFrame]] = contextvars.ContextVar(
    "ascent_feeds"
)
_current_snapshot: contextvars.ContextVar[datetime] = contextvars.ContextVar(
    "ascent_snapshot_timestamp"
)
_current_universe: contextvars.ContextVar[list[uuid.UUID]] = contextvars.ContextVar(
    "ascent_universe"
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
    """Get a parent feed's latest data inside a ``@feed(depends_on=...)`` function."""
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


def get_snapshot() -> datetime:
    """Return the current run's snapshot timestamp.

    This is the canonical "data-as-of" time — the value every persisted row
    carries and the value strategies downstream can use to align multi-feed
    snapshots. Available inside ``Feed.fetch()`` and ``Strategy.evaluate()``.
    """
    try:
        return _current_snapshot.get()
    except LookupError:
        raise RuntimeError(
            "get_snapshot() called outside of a feed/strategy run context."
        ) from None
