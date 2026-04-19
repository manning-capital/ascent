"""Runtime tests for :class:`FillHandlerService`.

Drives the service via a :class:`FakeDurableConsumer` so we can assert on
ack/nak behavior without a real broker. Successful fills are acked;
malformed payloads are acked (retries won't help); FillProcessor errors
trigger nak so the broker redelivers.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from ascent.application import FillHandlerService, FillProcessor, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.domain import OrderState, TradeState
from tests.fakes import (
    FakeClock,
    FakeDurableConsumer,
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def fixture():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow_factory = FakeUnitOfWorkFactory()
    exchange_id = uuid.uuid4()

    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
        is_paper=True,
    )
    processor = FillProcessor(
        trade_repo=trade_repo, order_repo=order_repo, event_bus=bus, uow_factory=uow_factory
    )
    consumer = FakeDurableConsumer()
    service = FillHandlerService(
        consumer=consumer,
        processor=processor,
        clock=FakeClock(NOW),
    )

    task = asyncio.create_task(service.run_forever())
    try:
        yield router, trade_repo, consumer, exchange_id
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_order_update_filled_drives_trade_to_open(fixture):
    router, trade_repo, consumer, exchange_id = fixture
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    trade = await trade_repo.get(None, draft.trade_id)
    order_id = trade.legs[0].entry_order.id

    msg = consumer.feed(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_update",
            "exchange_id": str(exchange_id),
            "order_id": str(order_id),
            "trade_id": str(draft.trade_id),
            "trade_leg_id": str(trade.legs[0].id),
            "response": {
                "exchange_order_id": "EX-001",
                "status": "FILLED",
                "filled_quantity": 1.0,
                "average_fill_price": 100.0,
            },
        },
        msg_id="1",
    )

    await asyncio.wait_for(msg._ack_event.wait(), timeout=1.0)

    t = await trade_repo.get(None, draft.trade_id)
    assert t.state == TradeState.OPEN
    assert t.legs[0].entry_price == 100.0


@pytest.mark.asyncio
async def test_non_order_update_actions_are_ignored_and_acked(fixture):
    _, _, consumer, exchange_id = fixture

    msg = consumer.feed(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_response",
            "response": {"exchange_order_id": "EX-1", "status": "SUBMITTED"},
        },
        msg_id="2",
    )
    await asyncio.wait_for(msg._ack_event.wait(), timeout=1.0)
    assert msg._acked is True


@pytest.mark.asyncio
async def test_unknown_status_string_is_acked_without_crashing_service(fixture):
    router, trade_repo, consumer, exchange_id = fixture
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    order_id = (await trade_repo.get(None, draft.trade_id)).legs[0].entry_order.id

    bad = consumer.feed(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_update",
            "order_id": str(order_id),
            "trade_id": str(draft.trade_id),
            "response": {"status": "NONSENSE"},
        },
        msg_id="3",
    )
    await asyncio.wait_for(bad._ack_event.wait(), timeout=1.0)

    good = consumer.feed(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_update",
            "order_id": str(order_id),
            "trade_id": str(draft.trade_id),
            "response": {
                "status": OrderState.FILLED.value,
                "filled_quantity": 1.0,
                "average_fill_price": 100.0,
            },
        },
        msg_id="4",
    )
    await asyncio.wait_for(good._ack_event.wait(), timeout=1.0)
    assert (await trade_repo.get(None, draft.trade_id)).state == TradeState.OPEN
