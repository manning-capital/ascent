"""SQLAlchemy adapter for :class:`ascent.ports.FeedRunRepository`."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.feeds import FeedRun
from ascent.domain import Context
from ascent.ports import FeedRunRepository


class SqlAlchemyFeedRunRepository(FeedRunRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    async def create(
        self,
        *,
        feed_id: uuid.UUID,
        started_at: datetime,
        snapshot_timestamp: datetime,
        context: Context | None = None,
    ) -> uuid.UUID:
        return await asyncio.to_thread(
            self._create_sync, feed_id, started_at, snapshot_timestamp, context
        )

    async def complete(self, run_id: uuid.UUID, *, at: datetime) -> None:
        await asyncio.to_thread(self._update_sync, run_id, "COMPLETED", at, None)

    async def fail(self, run_id: uuid.UUID, *, at: datetime, error_message: str) -> None:
        await asyncio.to_thread(self._update_sync, run_id, "FAILED", at, error_message)

    def _create_sync(
        self,
        feed_id: uuid.UUID,
        started_at: datetime,
        snapshot_timestamp: datetime,
        context: Context | None,
    ) -> uuid.UUID:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = FeedRun(
                feed_id=feed_id,
                snapshot_timestamp=snapshot_timestamp,
                status="RUNNING",
                started_at=started_at,
                context=context.model_dump(mode="json") if context is not None else None,
            )
            db.add(row)
            db.commit()
            return row.id

    def _update_sync(
        self, run_id: uuid.UUID, status: str, at: datetime, error_message: str | None
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = db.get(FeedRun, run_id)
            if row is None:
                return
            row.status = status
            row.completed_at = at
            if hasattr(row, "error_message"):
                row.error_message = error_message
            db.commit()
