"""SQLAlchemy adapter for :class:`ascent.ports.PartitionRepository`."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.feeds import FeedPartition
from ascent.ports import PartitionRepository


class SqlAlchemyPartitionRepository(PartitionRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    async def find_or_create(
        self,
        *,
        feed_id: uuid.UUID,
        key: datetime,
        window_start: datetime,
        window_end: datetime,
    ) -> uuid.UUID:
        return await asyncio.to_thread(
            self._find_or_create_sync, feed_id, key, window_start, window_end
        )

    async def set_status(self, partition_id: uuid.UUID, status: str) -> None:
        await asyncio.to_thread(self._set_status_sync, partition_id, status)

    def _find_or_create_sync(
        self,
        feed_id: uuid.UUID,
        key: datetime,
        window_start: datetime,
        window_end: datetime,
    ) -> uuid.UUID:
        with Session(bind=self._sf.kw["bind"]) as db:
            existing = (
                db.execute(
                    select(FeedPartition).where(
                        FeedPartition.feed_id == feed_id,
                        FeedPartition.partition_key == key,
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                return existing.id
            row = FeedPartition(
                feed_id=feed_id,
                partition_key=key,
                window_start=window_start,
                window_end=window_end,
                status="PENDING",
            )
            db.add(row)
            db.commit()
            return row.id

    def _set_status_sync(self, partition_id: uuid.UUID, status: str) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = db.get(FeedPartition, partition_id)
            if row is not None:
                row.status = status
                db.commit()
