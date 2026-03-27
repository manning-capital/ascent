"""``@persist`` decorator for custom feed persistence handlers.

Auto-persist (bulk upsert to the mapped EAV table) is the default behavior
and happens automatically in the DB-writer consumer.  ``@persist`` is
**optional** — use it only for additional/custom persistence logic beyond
the auto-persist (e.g., archiving, aggregation, notifications).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from ascent.feeds.decorator import Feed


class Persist:
    """Descriptor returned by the ``@persist`` decorator.

    Links a custom persistence function to a specific feed.  The DB-writer
    consumer runs all registered persist handlers after auto-persist.
    """

    def __init__(self, fn: Callable, feed: Feed) -> None:
        self.fn = fn
        self.feed = feed
        self.name = fn.__name__
        self.__name__ = fn.__name__
        self.__module__ = fn.__module__
        self.__qualname__ = fn.__qualname__
        self.__doc__ = fn.__doc__

        # Register on the feed
        feed._persist_handlers.append(self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def __repr__(self) -> str:
        return f"Persist({self.name!r}, feed={self.feed.__name__!r})"


def persist(feed_ref: Feed) -> Callable[[Callable], Persist]:
    """Decorator factory that links a custom persist function to a feed.

    Usage::

        @persist(market_data)
        def archive_prices(data: DataFrame[AssetAttributes], db: Session) -> None:
            ...
    """

    def decorator(fn: Callable) -> Persist:
        return Persist(fn, feed_ref)

    return decorator
