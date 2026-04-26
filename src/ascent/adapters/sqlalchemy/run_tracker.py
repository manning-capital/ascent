"""SQLAlchemy-backed :class:`ascent.ports.RunTrackerPort`.

Wraps :class:`SqlAlchemyFeedRunRepository` and :class:`SqlAlchemyStrategyRunRepository`
in an async context manager that creates the run row on enter and finalizes
it on exit.

``snapshot_timestamp`` is required at creation — the caller (``FeedExecutor``)
always knows the run's snapshot before opening the context.
"""

from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime

from ascent.domain import Context
from ascent.ports import FeedRunRepository, RunTrackerPort, StrategyRunRepository


class SqlAlchemyRunTracker(RunTrackerPort):
    def __init__(
        self,
        *,
        feed_run_repo: FeedRunRepository,
        strategy_run_repo: StrategyRunRepository,
    ) -> None:
        self._feeds = feed_run_repo
        self._strategies = strategy_run_repo

    def track_feed_run(
        self,
        feed_id: uuid.UUID,
        *,
        snapshot_timestamp: datetime,
        context: Context | None = None,
    ) -> AbstractAsyncContextManager[uuid.UUID]:
        return self._feed_ctx(feed_id, snapshot_timestamp, context)

    def track_strategy_run(self, strategy_id: uuid.UUID) -> AbstractAsyncContextManager[uuid.UUID]:
        return self._strategy_ctx(strategy_id)

    @asynccontextmanager
    async def _feed_ctx(
        self,
        feed_id: uuid.UUID,
        snapshot_timestamp: datetime,
        context: Context | None,
    ):
        started = datetime.now(tz=UTC)
        run_id = await self._feeds.create(
            feed_id=feed_id,
            started_at=started,
            snapshot_timestamp=snapshot_timestamp,
            context=context,
        )
        try:
            yield run_id
        except BaseException as exc:
            await self._feeds.fail(run_id, at=datetime.now(tz=UTC), error_message=str(exc))
            raise
        else:
            await self._feeds.complete(run_id, at=datetime.now(tz=UTC))

    @asynccontextmanager
    async def _strategy_ctx(self, strategy_id: uuid.UUID):
        started = datetime.now(tz=UTC)
        run_id = await self._strategies.create(strategy_id=strategy_id, started_at=started)
        try:
            yield run_id
        except BaseException as exc:
            await self._strategies.fail(run_id, at=datetime.now(tz=UTC), error_message=str(exc))
            raise
        else:
            await self._strategies.complete(run_id, at=datetime.now(tz=UTC))
