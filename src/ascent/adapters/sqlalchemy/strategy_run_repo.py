"""SQLAlchemy adapter for :class:`ascent.ports.StrategyRunRepository`."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.strategy import StrategyRun
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
from ascent.ports import StrategyRunRepository


class SqlAlchemyStrategyRunRepository(StrategyRunRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    async def create(self, *, strategy_id: uuid.UUID, started_at: datetime) -> uuid.UUID:
        return await asyncio.to_thread(self._create_sync, strategy_id, started_at)

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None:
        await asyncio.to_thread(self._update_sync, run_id, "COMPLETED", at, None)

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None:
        await asyncio.to_thread(self._update_sync, run_id, "FAILED", at, error_message)

    async def link_feed_runs(
        self,
        strategy_run_id: uuid.UUID,
        *,
        feed_run_ids: dict[uuid.UUID, uuid.UUID],
        trigger_feed_id: uuid.UUID,
    ) -> None:
        await asyncio.to_thread(self._link_sync, strategy_run_id, feed_run_ids, trigger_feed_id)

    def _create_sync(self, strategy_id: uuid.UUID, started_at: datetime) -> uuid.UUID:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = StrategyRun(
                strategy_id=strategy_id,
                status="RUNNING",
                started_at=started_at,
            )
            db.add(row)
            db.commit()
            return row.id

    def _update_sync(
        self, run_id: uuid.UUID, status: str, at: datetime, error_message: str | None
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = db.get(StrategyRun, run_id)
            if row is None:
                return
            row.status = status
            row.completed_at = at
            if hasattr(row, "error_message"):
                row.error_message = error_message
            db.commit()

    def _link_sync(
        self,
        strategy_run_id: uuid.UUID,
        feed_run_ids: dict[uuid.UUID, uuid.UUID],
        trigger_feed_id: uuid.UUID,
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            for feed_id, feed_run_id in feed_run_ids.items():
                db.add(
                    StrategyRunFeedRun(
                        strategy_run_id=strategy_run_id,
                        feed_run_id=feed_run_id,
                        feed_id=feed_id,
                        is_trigger=(feed_id == trigger_feed_id),
                    )
                )
            db.commit()
