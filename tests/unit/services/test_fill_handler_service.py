"""Runtime tests for :class:`FillHandlerService`.

This is where the "status string → OrderState enum" coercion lives, and
where a fill arriving on a stale trade reference would previously crash
the service loop. Every test spins the service up, drives events through
the bus, and asserts observable side effects.
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
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


async def _wait_for(predicate, *, timeout: float = 1.0):
    """Poll until ``predicate()`` returns truthy or the timeout fires."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = predicate()
        if result:
            return result
        await asyncio.sleep(0.005)
    raise AssertionError(f"predicate stayed falsy for {timeout}s")


@pytest_asyncio.fixture
async def fixture():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    exchange_id = uuid.uuid4()

    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
        is_paper=True,
    )
    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)
    service = FillHandlerService(
        response_channels=[f"ex.{exchange_id}.responses"],
        event_bus=bus,
        processor=processor,
        clock=FakeClock(NOW),
    )

    task = asyncio.create_task(service.run_forever())
    try:
        yield router, trade_repo, order_repo, bus, exchange_id
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_order_update_filled_drives_trade_to_open(fixture):
    router, trade_repo, _, bus, exchange_id = fixture

    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    trade = await trade_repo.get(draft.trade_id)
    order_id = trade.legs[0].entry_order.id

    # Simulate the exchange's fill event arriving on the responses channel.
    await bus.publish(
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
    )

    await _wait_for(
        lambda: asyncio.ensure_future(trade_repo.get(draft.trade_id)).done()
        or True  # kick the loop
    )

    # Actual assertion: state transitioned via the service.
    async def state_is_open():
        t = await trade_repo.get(draft.trade_id)
        return t.state == TradeState.OPEN

    for _ in range(200):
        if await state_is_open():
            break
        await asyncio.sleep(0.005)
    t = await trade_repo.get(draft.trade_id)
    assert t.state == TradeState.OPEN
    assert t.legs[0].entry_price == 100.0


@pytest.mark.asyncio
async def test_non_order_update_actions_are_ignored(fixture):
    router, trade_repo, _, bus, exchange_id = fixture
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)

    # A submit_order event on the response channel should be ignored — it's not
    # a fill. (Real exchange publishes order_response and order_update both
    # on the .responses channel.)
    await bus.publish(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_response",
            "response": {"exchange_order_id": "EX-1", "status": "SUBMITTED"},
        },
    )
    await asyncio.sleep(0.05)
    trade = await trade_repo.get(draft.trade_id)
    assert trade.state == TradeState.OPENING  # unchanged


@pytest.mark.asyncio
async def test_unknown_status_string_is_dropped_without_crashing_service(fixture):
    """An unknown status must not kill the service loop — other fills must
    keep being processed afterwards.
    """
    router, trade_repo, _, bus, exchange_id = fixture
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    order_id = (await trade_repo.get(draft.trade_id)).legs[0].entry_order.id

    # Garbage status — must be silently dropped.
    await bus.publish(
        f"ex.{exchange_id}.responses",
        {
            "action": "order_update",
            "order_id": str(order_id),
            "trade_id": str(draft.trade_id),
            "response": {"status": "NONSENSE"},
        },
    )

    # Follow with a valid fill — must still be processed.
    await bus.publish(
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
    )

    for _ in range(200):
        t = await trade_repo.get(draft.trade_id)
        if t.state == TradeState.OPEN:
            break
        await asyncio.sleep(0.005)
    assert (await trade_repo.get(draft.trade_id)).state == TradeState.OPEN
