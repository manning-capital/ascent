"""Integration test: outbox enqueue → real Postgres commit → OutboxRelay → fake broker.

Covers the phase-4 contract: a business write that enqueues into the
outbox becomes visible to the relay only after commit, the relay forwards
each row exactly once (per broker dedup), and rollback prevents any
relay activity.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import sessionmaker

from ascent.adapters.sqlalchemy.outbox import (
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
)
from ascent.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWorkFactory
from ascent.adapters.system_clock import SystemClock
from ascent.application.outbox_relay import OutboxRelay
from tests.fakes import FakeDurablePublisher

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


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


@pytest.fixture
def durable_publisher():
    return FakeDurablePublisher(dedup=True)


@pytest.fixture
def relay(uow_factory, reader, durable_publisher):
    return OutboxRelay(
        uow_factory=uow_factory,
        reader=reader,
        publisher=durable_publisher,
        clock=SystemClock(),
        # Zero lag so the test doesn't have to sleep 100ms between enqueue
        # and drain. In production the lag guards against reading a row
        # before its producing txn is visible to other sessions.
        commit_visibility_lag_ms=0,
    )


@pytest.mark.asyncio
async def test_enqueue_drain_end_to_end(uow_factory, publisher, relay, durable_publisher):
    async with uow_factory() as uow:
        await publisher.enqueue(
            uow.session,
            channel="ascent.exchange.e1",
            subject="ascent.exchange.e1",
            payload={"v": 1},
        )
        await publisher.enqueue(
            uow.session,
            channel="ascent.exchange.e1",
            subject="ascent.exchange.e1",
            payload={"v": 2},
        )

    drained = await relay.drain_once()
    assert drained == 2
    payloads = [p.payload["v"] for p in durable_publisher.published]
    assert payloads == [1, 2]


@pytest.mark.asyncio
async def test_rollback_prevents_relay_from_seeing_row(
    uow_factory, publisher, relay, durable_publisher
):
    with pytest.raises(RuntimeError, match="boom"):
        async with uow_factory() as uow:
            await publisher.enqueue(uow.session, channel="c", subject="s", payload={"v": 1})
            raise RuntimeError("boom")

    drained = await relay.drain_once()
    assert drained == 0
    assert durable_publisher.published == []


@pytest.mark.asyncio
async def test_second_drain_is_noop_after_first_marks_published(
    uow_factory, publisher, relay, durable_publisher
):
    async with uow_factory() as uow:
        await publisher.enqueue(uow.session, channel="c", subject="s", payload={})

    assert await relay.drain_once() == 1
    assert await relay.drain_once() == 0
    assert len(durable_publisher.published) == 1


@pytest.mark.asyncio
async def test_concurrent_relays_do_not_double_publish(
    uow_factory, publisher, reader, durable_publisher
):
    """Two relay instances running concurrently against the same outbox:
    SKIP LOCKED + broker dedup guarantees every row lands at the broker
    exactly once (or "at least once" from the relay's view, at most once
    from the broker's dedup view).
    """
    async with uow_factory() as uow:
        for i in range(20):
            await publisher.enqueue(uow.session, channel="c", subject="s", payload={"i": i})

    r1 = OutboxRelay(
        uow_factory=uow_factory,
        reader=reader,
        publisher=durable_publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
        batch_size=5,
    )
    r2 = OutboxRelay(
        uow_factory=uow_factory,
        reader=reader,
        publisher=durable_publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
        batch_size=5,
    )

    async def _drain_repeatedly(relay: OutboxRelay, rounds: int = 10) -> None:
        for _ in range(rounds):
            drained = await relay.drain_once()
            if drained == 0:
                return
            await asyncio.sleep(0)

    await asyncio.gather(_drain_repeatedly(r1), _drain_repeatedly(r2))

    # Every message landed at the broker exactly once.
    values = sorted(p.payload["i"] for p in durable_publisher.published)
    assert values == list(range(20))


@pytest.mark.asyncio
async def test_relay_crash_recovery_does_not_double_publish_with_dedup(
    uow_factory, publisher, reader, durable_publisher
):
    """Simulate a relay that publishes but crashes before mark_published:

    1. Relay claims and publishes row. We abort the UoW before mark runs.
    2. A second relay run re-claims the still-unpublished row.
    3. Broker dedup on msg_id keeps it at count=1.
    """
    async with uow_factory() as uow:
        await publisher.enqueue(uow.session, channel="c", subject="s", payload={"v": 1})

    # Drive the relay's steps manually to simulate a crash between
    # publish() and mark_published().
    async with uow_factory() as uow:
        claimed = await reader.claim_batch(uow.session, commit_visibility_lag_ms=0)
        assert len(claimed) == 1
        await durable_publisher.publish(
            claimed[0].subject, claimed[0].payload, msg_id=str(claimed[0].id)
        )
        # *crash* — UoW context exits without calling mark_published. The
        # UoW commits (no exception raised), but the row stays unpublished.

    # Second relay run: re-claims and re-publishes. Broker dedups.
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=reader,
        publisher=durable_publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
    )
    await relay.drain_once()

    # Exactly one copy at the broker despite two publish calls.
    assert len(durable_publisher.published) == 1
