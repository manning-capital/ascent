"""Runtime tests for :class:`ExchangeService`.

Post-phase-7 ExchangeService owns only the fill-watch loops (poll/stream)
and startup reconciliation. Dispatch lives in DispatcherService, and
response publications go through a :class:`DurablePublisher` (JetStream in
prod, :class:`FakeDurablePublisher` here).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import ExchangeService, FillProcessor, OrderReconciler, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import (
    FakeClock,
    FakeDurablePublisher,
    FakeExchange,
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


async def _wait(predicate, *, timeout: float = 1.0):
    for _ in range(int(timeout * 200)):
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"predicate stayed falsy for {timeout}s")


@pytest.fixture
def wiring():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    uow_factory = FakeUnitOfWorkFactory()
    clock = FakeClock(NOW)
    processor = FillProcessor(
        trade_repo=trade_repo, order_repo=order_repo, event_bus=bus, uow_factory=uow_factory
    )
    reconciler = OrderReconciler(
        order_repo=order_repo, fill_processor=processor, uow_factory=uow_factory
    )
    exchange_id = uuid.uuid4()
    responses_subject = f"ascent.exchange.{exchange_id}.responses"
    return trade_repo, order_repo, bus, clock, reconciler, exchange_id, responses_subject


@pytest.mark.asyncio
async def test_poll_monitor_publishes_state_change_for_tracked_order(wiring):
    _, _, _, clock, reconciler, exchange_id, responses_subject = wiring
    exchange = FakeExchange()
    exchange.poll_interval = 0.01
    exchange.supports_polling = True
    publisher = FakeDurablePublisher(dedup=True)

    open_orders: dict[str, dict] = {
        "EX-999": {
            "order_id": "o-1",
            "trade_id": "t-1",
            "trade_leg_id": "l-1",
            "last_status": None,
            "last_filled": 0.0,
        }
    }
    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        responses_subject=responses_subject,
        responses_publisher=publisher,
        reconciler=reconciler,
        clock=clock,
        open_orders=open_orders,
    )

    exchange.open_orders.append(
        OrderStatusResponse(
            exchange_order_id="EX-999",
            status="FILLED",
            filled_quantity=1.0,
            average_fill_price=100.0,
        )
    )

    task = asyncio.create_task(service.run_forever())
    try:
        await _wait(
            lambda: any(
                p.payload.get("action") == "order_update"
                and p.payload["response"].get("status") == "FILLED"
                for p in publisher.published
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
    trade_repo, order_repo, bus, clock, _, exchange_id, responses_subject = wiring
    uow_factory = FakeUnitOfWorkFactory()
    outbox = InMemoryOutboxPublisher()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
        is_paper=True,
    )
    draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    order_id = (await trade_repo.get(None, draft.trade_id)).legs[0].entry_order.id
    await order_repo.set_external_id(None, order_id, "EX-RECONCILE")

    processor = FillProcessor(
        trade_repo=trade_repo, order_repo=order_repo, event_bus=bus, uow_factory=uow_factory
    )
    reconciler = OrderReconciler(
        order_repo=order_repo, fill_processor=processor, uow_factory=uow_factory
    )

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
    publisher = FakeDurablePublisher(dedup=True)

    service = ExchangeService(
        exchange_id=exchange_id,
        exchange=exchange,
        responses_subject=responses_subject,
        responses_publisher=publisher,
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
