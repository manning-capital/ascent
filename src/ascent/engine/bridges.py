"""Sync/async bridges between the engine runtime and user code.

User feeds expose a sync :meth:`Feed.fetch` and user strategies expose a sync
:meth:`Strategy.evaluate`. The engine runs fully async. These glue types
translate between the two without leaking infrastructure into user code:

- :class:`_FeedFetcherBridge` wraps sync :meth:`Feed.fetch` as an async
  ``FeedFetcher``. Each tick, it loads the feed's active universe, sets the
  engine's contextvars, then runs user code on a threadpool.
- :class:`_SyncRouterProxy` adapts the async ``TradeRouter`` to sync calls
  from within ``evaluate()`` running on a worker thread.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import uuid
from typing import Any

from ascent.application import FeedFetcher
from ascent.domain import OrderType
from ascent.engine.context import (
    _current_feeds,
    _current_logger,
    _current_snapshot,
    _current_universe,
)

logger = logging.getLogger(__name__)


def _fetcher_factory(
    feed_cls: type,
    parameters: dict,
    *,
    feed_id: uuid.UUID,
    is_composite_scoped: bool,
    session_factory,
) -> Any:
    """Return a factory that builds a FeedFetcher for one execution tick.

    The factory is given the snapshot timestamp and parent-feed context; it
    returns a ``FeedFetcher`` whose ``fetch`` method runs user code on a
    threadpool and sets the Ascent contextvars before the call.
    """

    def factory(snapshot_timestamp, context):  # noqa: ANN001
        return _FeedFetcherBridge(
            feed_cls=feed_cls,
            parameters=parameters,
            feed_id=feed_id,
            is_composite_scoped=is_composite_scoped,
            session_factory=session_factory,
        )

    return factory


class _FeedFetcherBridge(FeedFetcher):
    def __init__(
        self,
        feed_cls: type,
        parameters: dict,
        *,
        feed_id: uuid.UUID,
        is_composite_scoped: bool,
        session_factory,
    ) -> None:
        self._feed_cls = feed_cls
        self._parameters = parameters
        self._feed_id = feed_id
        self._is_composite_scoped = is_composite_scoped
        self._session_factory = session_factory
        self._instance = feed_cls(parameters)

    async def fetch(self, snapshot_timestamp, context):  # noqa: ANN001
        def _call() -> Any:
            universe = self._load_universe(snapshot_timestamp)
            token_universe = _current_universe.set(universe)
            token_feeds = _current_feeds.set(context) if context else None
            token_snapshot = _current_snapshot.set(snapshot_timestamp)
            token_logger = _current_logger.set(logger)
            try:
                return self._instance.fetch()
            finally:
                _current_logger.reset(token_logger)
                _current_snapshot.reset(token_snapshot)
                if token_feeds is not None:
                    _current_feeds.reset(token_feeds)
                _current_universe.reset(token_universe)

        return await asyncio.to_thread(_call)

    def _load_universe(self, snapshot_timestamp: _dt.datetime) -> list[uuid.UUID]:
        """Read the feed's active scope as-of the run's snapshot_timestamp.

        Reads the bitemporal scope tables — rows whose interval
        ``[added_at, dropped_at)`` covers ``snapshot_timestamp``. This is
        the canonical "what was in scope at run-start" answer that
        downstream context reconstruction uses.
        """
        from sqlalchemy import or_, select

        from ascent.database.models.feeds import FeedCompositeScope, FeedInstrumentScope

        with self._session_factory() as db:
            if self._is_composite_scoped:
                rows = db.execute(
                    select(FeedCompositeScope.composite_id)
                    .where(FeedCompositeScope.feed_id == self._feed_id)
                    .where(FeedCompositeScope.added_at <= snapshot_timestamp)
                    .where(
                        or_(
                            FeedCompositeScope.dropped_at.is_(None),
                            FeedCompositeScope.dropped_at > snapshot_timestamp,
                        )
                    )
                    .order_by(FeedCompositeScope.order)
                ).all()
            else:
                rows = db.execute(
                    select(FeedInstrumentScope.instrument_id)
                    .where(FeedInstrumentScope.feed_id == self._feed_id)
                    .where(FeedInstrumentScope.added_at <= snapshot_timestamp)
                    .where(
                        or_(
                            FeedInstrumentScope.dropped_at.is_(None),
                            FeedInstrumentScope.dropped_at > snapshot_timestamp,
                        )
                    )
                    .order_by(FeedInstrumentScope.order)
                ).all()
        return [r[0] for r in rows]

    async def on_error(self, error: BaseException) -> None:
        await asyncio.to_thread(self._instance.on_error, error)


class _SyncRouterProxy:
    """Calls the async TradeRouter from a sync ``evaluate()`` running on a worker thread.

    Captures the main event loop at construction time so
    ``asyncio.run_coroutine_threadsafe`` has something to target. Returns the
    ``TradeDraft`` dataclass unchanged — user code accesses ``result.state`` /
    ``result.trade_id`` / ``result.leg_summaries`` directly.
    """

    def __init__(self, router, loop: asyncio.AbstractEventLoop) -> None:
        self._router = router
        self._loop = loop

    def submit(self, **kwargs):
        kwargs.setdefault("order_type", OrderType.MARKET)
        if isinstance(kwargs["order_type"], str):
            kwargs["order_type"] = OrderType(kwargs["order_type"])

        now = _dt.datetime.now(tz=_dt.UTC)
        return _run_in_loop(self._router.submit(now=now, **kwargs), self._loop)

    def close(self, **kwargs):
        if isinstance(kwargs.get("order_type"), str):
            kwargs["order_type"] = OrderType(kwargs["order_type"])

        now = _dt.datetime.now(tz=_dt.UTC)
        return _run_in_loop(self._router.close(now=now, **kwargs), self._loop)

    def get_open_trades(self):
        return _run_in_loop(self._router.get_open_trades(), self._loop)


def _run_in_loop(coro, loop: asyncio.AbstractEventLoop):
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
