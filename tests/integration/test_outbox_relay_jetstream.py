"""End-to-end integration test: outbox row → OutboxRelay → NATS JetStream → consumer.

This is the real path the engine will use in production. It replaces the
phase-4 shim (Redis pub/sub) with the phase-5 target (NATS JetStream). The
specific invariants under test:

- A committed outbox row is forwarded to JetStream and received by a
  durable consumer.
- Crash recovery between publish and mark_published does NOT produce a
  duplicate at the broker — ``Nats-Msg-Id`` dedup absorbs the second
  publish within the dedup window.
- Two concurrent relay workers do not double-publish (SKIP LOCKED + broker
  dedup both hold).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.orm import sessionmaker

from ascent.adapters.nats import (
    NatsJetStreamConsumer,
    NatsJetStreamPublisher,
    connect_nats,
    ensure_stream,
)
from ascent.adapters.sqlalchemy.outbox import (
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
)
from ascent.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWorkFactory
from ascent.adapters.system_clock import SystemClock
from ascent.application.outbox_relay import OutboxRelay


@pytest.fixture
def session_factory(postgres_engine) -> sessionmaker:
    return sessionmaker(bind=postgres_engine)


@pytest.fixture
def uow_factory(session_factory):
    return SqlAlchemyUnitOfWorkFactory(session_factory)


@pytest.fixture
def outbox_publisher():
    return SqlAlchemyOutboxPublisher()


@pytest.fixture
def outbox_reader():
    return SqlAlchemyOutboxReader()


@pytest_asyncio.fixture
async def nats_client(nats_url):
    nc = await connect_nats(nats_url, name="ascent-e2e")
    try:
        yield nc
    finally:
        await nc.close()


@pytest_asyncio.fixture
async def stream(nats_client):
    name = f"ASCENT_E2E_{uuid.uuid4().hex[:8]}"
    await ensure_stream(
        nats_client,
        stream_name=name,
        subjects=[f"ascent.e2e.{name}.>"],
        duplicate_window_seconds=120,
    )
    yield name
    try:
        await nats_client.jetstream().delete_stream(name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_enqueue_relay_jetstream_consume_end_to_end(
    uow_factory, outbox_publisher, outbox_reader, nats_client, stream
):
    subject = f"ascent.e2e.{stream}.orders"
    publisher = NatsJetStreamPublisher(nats_client)
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=outbox_reader,
        publisher=publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
    )

    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=stream,
        subject_filter=subject,
        durable_name="e2e-dispatcher",
        fetch_timeout=0.5,
    )

    async with uow_factory() as uow:
        for i in range(3):
            await outbox_publisher.enqueue(
                uow.session, channel=subject, subject=subject, payload={"i": i}
            )

    published = await relay.drain_once()
    assert published == 3

    received: list[dict] = []
    async with asyncio.timeout(5.0):
        async for msg in consumer:
            received.append(msg.payload)
            await msg.ack()
            if len(received) == 3:
                break
    await consumer.aclose()

    assert sorted(p["i"] for p in received) == [0, 1, 2]


@pytest.mark.asyncio
async def test_crash_recovery_does_not_duplicate_at_broker(
    uow_factory, outbox_publisher, outbox_reader, nats_client, stream
):
    """Simulate: relay publishes to NATS, then crashes before marking published.
    On restart, it re-publishes. JetStream dedups on ``Nats-Msg-Id``, so the
    consumer receives exactly one copy."""
    subject = f"ascent.e2e.{stream}.orders"
    publisher = NatsJetStreamPublisher(nats_client)

    async with uow_factory() as uow:
        await outbox_publisher.enqueue(
            uow.session, channel=subject, subject=subject, payload={"v": 1}
        )

    # First pass: claim + publish but abort the UoW before mark_published.
    async with uow_factory() as uow:
        claimed = await outbox_reader.claim_batch(uow.session, commit_visibility_lag_ms=0)
        assert len(claimed) == 1
        await publisher.publish(claimed[0].subject, claimed[0].payload, msg_id=str(claimed[0].id))
        # *crash* — UoW context exits cleanly (we never called mark_published),
        # so the row stays unpublished and will be re-claimed.

    # Second pass: a real relay does the full claim-publish-mark cycle.
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=outbox_reader,
        publisher=publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
    )
    published = await relay.drain_once()
    assert published == 1

    # Consume — broker dedup must have collapsed the two publishes into one.
    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=stream,
        subject_filter=subject,
        durable_name="crash-recovery",
        fetch_timeout=0.5,
    )
    received: list[dict] = []
    try:
        async with asyncio.timeout(3.0):
            async for msg in consumer:
                received.append(msg.payload)
                await msg.ack()
                if len(received) >= 2:
                    break
    except TimeoutError:
        pass
    await consumer.aclose()

    assert received == [{"v": 1}]


@pytest.mark.asyncio
async def test_concurrent_relays_deliver_every_message_exactly_once(
    uow_factory, outbox_publisher, outbox_reader, nats_client, stream
):
    subject = f"ascent.e2e.{stream}.orders"
    publisher = NatsJetStreamPublisher(nats_client)

    async with uow_factory() as uow:
        for i in range(10):
            await outbox_publisher.enqueue(
                uow.session, channel=subject, subject=subject, payload={"i": i}
            )

    # Two relays running concurrently.
    def _make_relay() -> OutboxRelay:
        return OutboxRelay(
            uow_factory=uow_factory,
            reader=outbox_reader,
            publisher=publisher,
            clock=SystemClock(),
            commit_visibility_lag_ms=0,
            batch_size=3,
        )

    r1, r2 = _make_relay(), _make_relay()

    async def _drain_until_empty(relay: OutboxRelay) -> None:
        for _ in range(20):
            if await relay.drain_once() == 0:
                return
            await asyncio.sleep(0)

    await asyncio.gather(_drain_until_empty(r1), _drain_until_empty(r2))

    # Consume and verify every i in 0..9 landed exactly once.
    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=stream,
        subject_filter=subject,
        durable_name="concurrent-relay",
        fetch_timeout=0.5,
    )
    received: list[int] = []
    try:
        async with asyncio.timeout(5.0):
            async for msg in consumer:
                received.append(msg.payload["i"])
                await msg.ack()
                if len(received) == 10:
                    break
    except TimeoutError:
        pass
    await consumer.aclose()

    assert sorted(received) == list(range(10))
