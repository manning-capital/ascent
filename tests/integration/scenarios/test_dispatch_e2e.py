"""End-to-end dispatch integration test.

Drives the full Phase-4/5/6 pipeline against real infrastructure:

    TradeRouter.submit(UoW=real SA UoW)
        ↓  write Trade+Order+Outbox rows atomically to Postgres
    OutboxRelay
        ↓  claim with FOR UPDATE SKIP LOCKED, publish to JetStream
    NATS JetStream
        ↓  durable consumer delivers to
    DispatcherService
        ↓  calls FakeExchange.submit_order, acks on success
    FakeExchange.submissions  ← assertion site

Anchors the clean-architecture promise of the whole change: a single
business-layer call (``router.submit``) produces an atomic DB commit and
an exchange submission, with every layer independently testable.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.orm import sessionmaker

from ascent.adapters import (
    OrmMappers,
    SqlAlchemyOrderRepository,
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
    SqlAlchemyTradeRepository,
    SqlAlchemyUnitOfWorkFactory,
    TypeCache,
)
from ascent.adapters.nats import (
    NatsJetStreamConsumer,
    NatsJetStreamPublisher,
    connect_nats,
    ensure_stream,
)
from ascent.adapters.system_clock import SystemClock
from ascent.application import (
    DispatcherService,
    OutboxRelay,
    TradeRouter,
)
from ascent.application.route_trade import ExchangeBinding
from tests.fakes import FakeExchange, InMemoryEventBus

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def nats_client(nats_url):
    nc = await connect_nats(nats_url, name="ascent-scenario")
    try:
        yield nc
    finally:
        await nc.close()


@pytest_asyncio.fixture
async def stream(nats_client):
    # Per-test stream keeps tests isolated.
    name = f"SCENARIO_{uuid.uuid4().hex[:8]}"
    await ensure_stream(
        nats_client,
        stream_name=name,
        subjects=[f"scenario.{name}.>"],
        duplicate_window_seconds=120,
    )
    yield name
    try:
        await nats_client.jetstream().delete_stream(name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_router_submit_end_to_end_reaches_exchange(
    postgres_engine, seeded_ids, nats_client, stream
):
    session_factory = sessionmaker(bind=postgres_engine)
    type_cache = TypeCache(session_factory)
    mappers = OrmMappers(type_cache)
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)

    trade_repo = SqlAlchemyTradeRepository(type_cache, mappers)
    order_repo = SqlAlchemyOrderRepository(type_cache, mappers)
    outbox_pub = SqlAlchemyOutboxPublisher()
    outbox_reader = SqlAlchemyOutboxReader()

    bus = InMemoryEventBus()  # responses channel is still Redis-style
    dispatch_subject = f"scenario.{stream}.dispatch"

    router = TradeRouter(
        strategy_id=seeded_ids.strategy_id,
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox_pub,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=seeded_ids.exchange_id, channel=dispatch_subject)],
        is_paper=True,
    )

    js_publisher = NatsJetStreamPublisher(nats_client)
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=outbox_reader,
        publisher=js_publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
    )

    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=stream,
        subject_filter=dispatch_subject,
        durable_name="scenario-dispatcher",
        fetch_timeout=0.3,
    )
    exchange = FakeExchange()
    dispatcher = DispatcherService(
        exchange_id=seeded_ids.exchange_id,
        exchange=exchange,
        consumer=consumer,
        responses_subject=f"{dispatch_subject}.responses",
        responses_publisher=js_publisher,
        clock=SystemClock(),
    )

    dispatcher_task = asyncio.create_task(dispatcher.run_forever())
    try:
        # Act: submit one trade. Produces 1 Trade + 1 Order + 1 Outbox row atomically.
        draft = await router.submit(
            side="BUY",
            target_id=seeded_ids.instrument_id_a,
            quantity=1.0,
            now=NOW,
        )

        # Relay claims + forwards to JetStream.
        published = await relay.drain_once()
        assert published == 1

        # Dispatcher consumes + submits to the FakeExchange. Wait for it.
        for _ in range(200):
            if len(exchange.submissions) == 1:
                break
            await asyncio.sleep(0.01)

        assert len(exchange.submissions) == 1
        assert exchange.submissions[0].quantity == 1.0
        assert exchange.submissions[0].side == "BUY"

        # And the dispatcher published an order_response back to JetStream.
        # A dedicated consumer on the responses subject picks it up.
        response_consumer = NatsJetStreamConsumer(
            nats_client,
            stream=stream,
            subject_filter=f"{dispatch_subject}.responses",
            durable_name="scenario-response-watcher",
            fetch_timeout=0.3,
        )
        received: list[dict] = []
        try:
            async with asyncio.timeout(3.0):
                async for msg in response_consumer:
                    received.append(msg.payload)
                    await msg.ack()
                    if received:
                        break
        except TimeoutError:
            pass
        await response_consumer.aclose()
        assert received
        assert received[0]["action"] == "order_response"
        assert received[0]["trade_id"] == str(draft.trade_id)
    finally:
        dispatcher_task.cancel()
        try:
            await dispatcher_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_rollback_on_submit_prevents_exchange_dispatch(
    postgres_engine, seeded_ids, nats_client, stream
):
    """If the router's UoW rolls back, the outbox row is gone and the
    exchange never sees the submission. This is the atomicity guarantee."""
    session_factory = sessionmaker(bind=postgres_engine)
    type_cache = TypeCache(session_factory)
    mappers = OrmMappers(type_cache)
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)

    trade_repo = SqlAlchemyTradeRepository(type_cache, mappers)
    order_repo = SqlAlchemyOrderRepository(type_cache, mappers)
    outbox_pub = SqlAlchemyOutboxPublisher()
    outbox_reader = SqlAlchemyOutboxReader()

    bus = InMemoryEventBus()
    dispatch_subject = f"scenario.{stream}.rollback"

    class _ExplodingOutbox:
        """Mirrors SqlAlchemyOutboxPublisher but raises mid-enqueue to force
        the UoW to roll back. Used only in this test — the rollback path is
        what we care about verifying end-to-end."""

        def __init__(self, real):
            self._real = real

        async def enqueue(self, session, *, channel, subject, payload):
            await self._real.enqueue(session, channel=channel, subject=subject, payload=payload)
            raise RuntimeError("forced failure after enqueue")

    router = TradeRouter(
        strategy_id=seeded_ids.strategy_id,
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=_ExplodingOutbox(outbox_pub),
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=seeded_ids.exchange_id, channel=dispatch_subject)],
        is_paper=True,
    )

    js_publisher = NatsJetStreamPublisher(nats_client)
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=outbox_reader,
        publisher=js_publisher,
        clock=SystemClock(),
        commit_visibility_lag_ms=0,
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        await router.submit(
            side="BUY",
            target_id=seeded_ids.instrument_id_a,
            quantity=1.0,
            now=NOW,
        )

    # UoW rolled back → outbox is empty → relay has nothing to publish.
    drained = await relay.drain_once()
    assert drained == 0
