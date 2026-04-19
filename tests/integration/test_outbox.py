"""Integration tests for :class:`SqlAlchemyOutboxPublisher` + reader.

Covers the guarantees the design doc leans on:
- An enqueue inside a UoW is atomic with the business write that preceded it.
- A rollback drops both the business write AND the outbox row.
- ``claim_batch`` with ``FOR UPDATE SKIP LOCKED`` prevents two relay workers
  from claiming the same row.
- ``mark_published`` makes the row invisible to subsequent claims.
- The hypertable partitioning column (``created_at``) is respected — we
  write and read across the composite PK without Timescale complaining.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.adapters.sqlalchemy.outbox import (
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
)
from ascent.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWorkFactory
from ascent.database.models.event_outbox import EventOutbox
from ascent.database.models.types import AssetType


@pytest.fixture
def session_factory(postgres_engine) -> sessionmaker:
    return sessionmaker(bind=postgres_engine)


@pytest.fixture
def uow_factory(session_factory):
    return SqlAlchemyUnitOfWorkFactory(session_factory)


@pytest.fixture
def publisher():
    return SqlAlchemyOutboxPublisher()


@pytest.fixture
def reader():
    return SqlAlchemyOutboxReader()


@pytest.mark.asyncio
async def test_enqueue_commits_with_business_write(uow_factory, publisher, postgres_engine):
    async with uow_factory() as uow:
        uow.session.add(AssetType(name="ATOMIC_OK", display_name="Atomic Ok"))
        await publisher.enqueue(
            uow.session,
            channel="ascent.exchange.x",
            subject="ascent.exchange.x",
            payload={"v": 1},
        )

    with Session(postgres_engine) as verify:
        rows = verify.execute(select(EventOutbox)).scalars().all()
        assert len(rows) == 1
        assert rows[0].payload == {"v": 1}
        assert rows[0].published_at is None
        # Business row made it too.
        assert (
            verify.execute(
                select(AssetType).where(AssetType.name == "ATOMIC_OK")
            ).scalar_one_or_none()
            is not None
        )


@pytest.mark.asyncio
async def test_rollback_drops_both_business_write_and_outbox_row(
    uow_factory, publisher, postgres_engine
):
    with pytest.raises(RuntimeError, match="boom"):
        async with uow_factory() as uow:
            uow.session.add(AssetType(name="ATOMIC_ROLLBACK", display_name="Rollback"))
            await publisher.enqueue(uow.session, channel="c", subject="c", payload={"v": 1})
            raise RuntimeError("boom")

    with Session(postgres_engine) as verify:
        assert verify.execute(select(EventOutbox)).scalars().all() == []
        assert (
            verify.execute(
                select(AssetType).where(AssetType.name == "ATOMIC_ROLLBACK")
            ).scalar_one_or_none()
            is None
        )


@pytest.mark.asyncio
async def test_claim_batch_then_mark_published_removes_from_pool(uow_factory, publisher, reader):
    async with uow_factory() as uow:
        for i in range(3):
            await publisher.enqueue(uow.session, channel="c", subject="c", payload={"i": i})

    # Back-dated query for the visibility lag — we just inserted and the
    # default 100ms window would exclude everything.
    await asyncio.sleep(0.15)

    async with uow_factory() as uow:
        claimed = await reader.claim_batch(uow.session, limit=10)
        assert len(claimed) == 3
        await reader.mark_published(
            uow.session,
            ids=[(c.id, c.created_at) for c in claimed],
            published_at=datetime.now(tz=UTC),
        )

    async with uow_factory() as uow:
        again = await reader.claim_batch(uow.session, limit=10)
        assert again == []


@pytest.mark.asyncio
async def test_commit_visibility_lag_excludes_recent_rows(uow_factory, publisher, reader):
    async with uow_factory() as uow:
        await publisher.enqueue(uow.session, channel="c", subject="c", payload={})

    async with uow_factory() as uow:
        # With a 60-second lag, the just-committed row must not be returned.
        claimed = await reader.claim_batch(uow.session, commit_visibility_lag_ms=60_000)
        assert claimed == []


@pytest.mark.asyncio
async def test_skip_locked_prevents_double_claim(uow_factory, publisher, reader):
    """Two concurrent relay workers must NOT both claim the same row."""
    async with uow_factory() as uow:
        for i in range(2):
            await publisher.enqueue(uow.session, channel="c", subject="c", payload={"i": i})
    await asyncio.sleep(0.15)

    # Open two UoWs concurrently; each tries to claim 10 rows. With SKIP
    # LOCKED, the two batches must be disjoint.
    async def _claim_one(seen: list[list[int]]) -> None:
        async with uow_factory() as uow:
            claimed = await reader.claim_batch(uow.session, limit=10)
            # Hold the lock briefly so the other worker sees the row gone.
            await asyncio.sleep(0.1)
            seen.append([c.id for c in claimed])

    results: list[list[int]] = []
    await asyncio.gather(_claim_one(results), _claim_one(results))

    flat = [row_id for batch in results for row_id in batch]
    # Every id appears at most once across the two batches.
    assert len(flat) == len(set(flat))


@pytest.mark.asyncio
async def test_mark_published_increments_attempts(uow_factory, publisher, reader):
    async with uow_factory() as uow:
        await publisher.enqueue(uow.session, channel="c", subject="c", payload={})
    await asyncio.sleep(0.15)

    async with uow_factory() as uow:
        [claimed] = await reader.claim_batch(uow.session)
        await reader.mark_published(
            uow.session,
            ids=[(claimed.id, claimed.created_at)],
            published_at=datetime.now(tz=UTC),
        )

    with Session(uow_factory._sf.kw["bind"]) as verify:
        row = verify.execute(select(EventOutbox)).scalar_one()
        assert row.published_at is not None
        assert row.attempts == 1


@pytest.mark.asyncio
async def test_increment_attempts_keeps_row_claimable(uow_factory, publisher, reader):
    async with uow_factory() as uow:
        await publisher.enqueue(uow.session, channel="c", subject="c", payload={})
    await asyncio.sleep(0.15)

    async with uow_factory() as uow:
        [claimed] = await reader.claim_batch(uow.session)
        await reader.increment_attempts(uow.session, ids=[(claimed.id, claimed.created_at)])

    async with uow_factory() as uow:
        # Still unpublished → still claimable.
        [again] = await reader.claim_batch(uow.session)
        assert again.id == claimed.id
        assert again.attempts == 1


@pytest.mark.asyncio
async def test_claim_batch_ordered_by_created_at_then_id(uow_factory, publisher, reader):
    """Relay order is FIFO — partial failures don't reorder publications."""
    async with uow_factory() as uow:
        for i in range(5):
            await publisher.enqueue(uow.session, channel="c", subject="c", payload={"i": i})
    await asyncio.sleep(0.15)

    async with uow_factory() as uow:
        claimed = await reader.claim_batch(uow.session, limit=10)
        payloads = [c.payload["i"] for c in claimed]
        assert payloads == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_hypertable_partitioning_survives_past_chunks(
    uow_factory, publisher, reader, postgres_engine
):
    """Write a row with ``created_at`` in the past so it lands in a different
    Timescale chunk, then verify the relay can still find and mark it."""
    past = datetime.now(tz=UTC) - timedelta(days=2)
    with Session(postgres_engine) as db:
        # Insert directly with a back-dated created_at to force a separate chunk.
        db.add(
            EventOutbox(
                created_at=past,
                channel="c",
                subject="c",
                payload={"i": 0},
            )
        )
        db.commit()

    async with uow_factory() as uow:
        claimed = await reader.claim_batch(uow.session, limit=10)
        assert len(claimed) == 1
        assert claimed[0].created_at.year == past.year
        await reader.mark_published(
            uow.session,
            ids=[(claimed[0].id, claimed[0].created_at)],
            published_at=datetime.now(tz=UTC),
        )
