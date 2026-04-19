"""SQLAlchemy adapters for the outbox pattern.

Two pieces live here:

- :class:`SqlAlchemyOutboxPublisher` — writes outbox rows inside a UoW.
  Used by application code on the producer side.
- :class:`SqlAlchemyOutboxReader` — reads unpublished rows with
  ``FOR UPDATE SKIP LOCKED`` for the relay process, and marks them
  published once forwarded. Used only by the relay loop.

Both take a ``Session`` from the caller's UoW (or, in the relay's case,
from a relay-scoped UoW). Neither commits — the enclosing UoW does.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ascent.database.models.event_outbox import EventOutbox
from ascent.ports.outbox import OutboxPublisher


class SqlAlchemyOutboxPublisher(OutboxPublisher):
    async def enqueue(
        self,
        session: Session,
        *,
        channel: str,
        subject: str,
        payload: dict[str, Any],
    ) -> None:
        await asyncio.to_thread(self._enqueue_sync, session, channel, subject, payload)

    def _enqueue_sync(
        self,
        db: Session,
        channel: str,
        subject: str,
        payload: dict[str, Any],
    ) -> None:
        db.add(EventOutbox(channel=channel, subject=subject, payload=payload))
        db.flush()


@dataclass(frozen=True)
class OutboxRow:
    """Detached snapshot of an outbox row, safe to use after the reading
    session has been closed. The relay never mutates these — it writes
    back via :meth:`SqlAlchemyOutboxReader.mark_published`.
    """

    id: int
    created_at: datetime
    channel: str
    subject: str
    payload: dict[str, Any]
    attempts: int


class SqlAlchemyOutboxReader:
    """Relay-side access to the outbox table.

    ``claim_batch`` locks a batch of unpublished rows with ``SKIP LOCKED``
    so multiple relay workers can run concurrently without double-publishing.
    The caller must either call ``mark_published`` on each row it forwards
    successfully, or let the enclosing UoW roll back (which releases the lock
    and leaves the rows available for another worker).
    """

    async def claim_batch(
        self,
        session: Session,
        *,
        limit: int = 100,
        commit_visibility_lag_ms: int = 100,
    ) -> list[OutboxRow]:
        """Return up to ``limit`` unpublished rows, locked for this session.

        ``commit_visibility_lag_ms`` excludes rows newer than that window to
        avoid publishing an event before its producing transaction is
        actually visible to other sessions. 100ms is a safe default for
        single-node Postgres; tune up on replicated setups.
        """
        return await asyncio.to_thread(
            self._claim_batch_sync, session, limit, commit_visibility_lag_ms
        )

    def _claim_batch_sync(
        self,
        db: Session,
        limit: int,
        commit_visibility_lag_ms: int,
    ) -> list[OutboxRow]:
        stmt = (
            select(EventOutbox)
            .where(EventOutbox.published_at.is_(None))
            .where(
                EventOutbox.created_at < text(f"now() - interval '{commit_visibility_lag_ms} ms'")
            )
            .order_by(EventOutbox.created_at, EventOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = db.execute(stmt).scalars().all()
        return [
            OutboxRow(
                id=r.id,
                created_at=r.created_at,
                channel=r.channel,
                subject=r.subject,
                payload=r.payload,
                attempts=r.attempts,
            )
            for r in rows
        ]

    async def mark_published(
        self,
        session: Session,
        *,
        ids: list[tuple[int, datetime]],
        published_at: datetime,
    ) -> None:
        """Mark each ``(id, created_at)`` as published at the given time.

        Takes composite keys because ``event_outbox`` is a hypertable; the
        primary key is ``(id, created_at)``, and dropping the partitioning
        column makes Timescale unhappy on chunk operations.
        """
        if not ids:
            return
        await asyncio.to_thread(self._mark_published_sync, session, ids, published_at)

    def _mark_published_sync(
        self,
        db: Session,
        ids: list[tuple[int, datetime]],
        published_at: datetime,
    ) -> None:
        for row_id, created_at in ids:
            row = db.get(EventOutbox, (row_id, created_at))
            if row is None:
                continue
            row.published_at = published_at
            row.attempts = (row.attempts or 0) + 1
        db.flush()

    async def increment_attempts(
        self,
        session: Session,
        *,
        ids: list[tuple[int, datetime]],
    ) -> None:
        """Bump ``attempts`` without marking published. Used when a relay
        pass forwards the row to the broker but the broker ack was lost —
        we count the attempt so future backoff logic can react.
        """
        if not ids:
            return
        await asyncio.to_thread(self._increment_attempts_sync, session, ids)

    def _increment_attempts_sync(
        self,
        db: Session,
        ids: list[tuple[int, datetime]],
    ) -> None:
        for row_id, created_at in ids:
            row = db.get(EventOutbox, (row_id, created_at))
            if row is None:
                continue
            row.attempts = (row.attempts or 0) + 1
        db.flush()
