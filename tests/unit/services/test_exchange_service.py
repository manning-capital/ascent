"""Runtime tests for :class:`ExchangeService`.

Responsibilities under test:
- Reconciler runs once on startup.
- Dispatch loop routes ``submit_order`` events to ``ExchangePort.submit_order``
  and publishes the ack back on the responses channel.
- Poll-monitor publishes state changes for tracked orders.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import ExchangeService, FillProcessor, OrderReconciler
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import (
    FakeClock,
    FakeExchange,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


async def _wait(predicate, *, timeout: float = 1.0):
    for _ in range(int(timeout * 200)):
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"predicate stayed falsy for {timeout}s")


async def _let_subscribed(bus, channel: str, *, timeout: float = 0.5):
    for _ in range(int(timeout * 200)):
        if bus._subscribers.get(channel):
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"service never subscribed to {channel}")


@pytest.fixture
def wiring():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    clock = FakeClock(NOW)
    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)
    reconciler = OrderReconciler(order_repo=order_repo, fill_processor=processor)
    exchange_id = uuid.uuid4()
    channel = f"ex.{exchange_id}"
    return trade_repo, order_repo, bus, clock, reconciler, exchange_id, channel


@pytest.mark.asyncio
async def test_dispatch_submit_order_forwards_to_exchange_and_acks(wiring):
    _, _, bus, clock, reconciler, exchange_id, channel = wiring
    exchange = FakeExchange()
    exchange.supports_polling = False  # only test the dispatch loop here

    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        channel=channel,
        event_bus=bus,
        reconciler=reconciler,
        clock=clock,
    )

    task = asyncio.create_task(service.run_forever())
    try:
        await _let_subscribed(bus, channel)
        await bus.publish(
            channel,
            {
                "action": "submit_order",
                "order_id": str(uuid.uuid4()),
                "trade_id": str(uuid.uuid4()),
                "trade_leg_id": str(uuid.uuid4()),
                "order": {
                    "order_type": "MARKET",
                    "side": "BUY",
                    "from_asset_symbol": "BTC",
                    "to_asset_symbol": "USD",
                    "quantity": 1.0,
                    "price": None,
                },
            },
        )
        await _wait(lambda: len(exchange.submissions) == 1)
        # A response must be published back on the .responses channel.
        await _wait(
            lambda: any(
                e.channel == f"{channel}.responses" and e.payload.get("action") == "order_response"
                for e in bus.published
            )
        )
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_cancel_order_publishes_update(wiring):
    _, _, bus, clock, reconciler, exchange_id, channel = wiring
    exchange = FakeExchange()
    exchange.supports_polling = False
    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        channel=channel,
        event_bus=bus,
        reconciler=reconciler,
        clock=clock,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        await _let_subscribed(bus, channel)
        await bus.publish(
            channel,
            {"action": "cancel_order", "exchange_order_id": "EX-123"},
        )
        await _wait(
            lambda: any(
                e.channel == f"{channel}.responses"
                and e.payload.get("action") == "order_update"
                and e.payload["response"]["status"] == "CANCELLED"
                for e in bus.published
            )
        )
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_poll_monitor_publishes_state_change(wiring):
    _, _, bus, clock, reconciler, exchange_id, channel = wiring
    exchange = FakeExchange()
    exchange.poll_interval = 0.01  # fast poll for tests
    exchange.supports_polling = True

    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        channel=channel,
        event_bus=bus,
        reconciler=reconciler,
        clock=clock,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        await _let_subscribed(bus, channel)
        # Submit so the service registers the order in its open_orders map.
        await bus.publish(
            channel,
            {
                "action": "submit_order",
                "order_id": "o-1",
                "trade_id": "t-1",
                "trade_leg_id": "l-1",
                "order": {
                    "order_type": "MARKET",
                    "side": "BUY",
                    "from_asset_symbol": "BTC",
                    "to_asset_symbol": "USD",
                    "quantity": 1.0,
                    "price": None,
                },
            },
        )
        await _wait(lambda: len(exchange.submissions) == 1)
        exchange.submissions[0].client_order_id  # None
        # Use the generated exchange_order_id from the fake's response.
        await _wait(lambda: service.open_orders)
        ex_order_id = next(iter(service.open_orders))

        # Now simulate the exchange reporting a fill.
        exchange.open_orders.append(
            OrderStatusResponse(
                exchange_order_id=ex_order_id,
                status="FILLED",
                filled_quantity=1.0,
                average_fill_price=100.0,
            )
        )

        await _wait(
            lambda: any(
                e.channel == f"{channel}.responses"
                and e.payload.get("action") == "order_update"
                and e.payload["response"].get("status") == "FILLED"
                for e in bus.published
            )
        )
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_reconciler_runs_once_at_startup(wiring):
    trade_repo, order_repo, bus, clock, _, exchange_id, channel = wiring

    # Seed a stale entry order + its trade so the reconciler finds something.
    from ascent.application import TradeRouter
    from ascent.application.route_trade import ExchangeBinding

    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=channel)],
        is_paper=True,
    )
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    order_id = (await trade_repo.get(draft.trade_id)).legs[0].entry_order.id
    await order_repo.set_external_id(order_id, "EX-RECONCILE")

    processor = FillProcessor(trade_repo=trade_repo, order_repo=order_repo, event_bus=bus)
    reconciler = OrderReconciler(order_repo=order_repo, fill_processor=processor)

    exchange = FakeExchange()
    exchange.supports_polling = False
    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-RECONCILE",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=99.0,
        )
    )

    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        channel=channel,
        event_bus=bus,
        reconciler=reconciler,
        clock=clock,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        from ascent.domain import TradeState

        await _wait(
            lambda: (
                trade_repo._trades.get(draft.trade_id) is not None
                and trade_repo._trades[draft.trade_id].state == TradeState.OPEN
            )
        )
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
