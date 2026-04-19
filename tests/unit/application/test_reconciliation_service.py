"""Tests for :class:`PeriodicReconciliationService`.

Layer 2 defense-in-depth against stuck trades. The existing
:class:`OrderReconciler` pulls exchange state for every non-terminal order
and synthesizes a :class:`FillEvent` per stale order. Running it once on
startup handles restart scenarios; running it on an interval handles the
long tail — a dropped fill event, a transient broker hiccup, anything
that left a trade non-terminal when the exchange says otherwise.

These tests pin the service's behavior:

- First reconcile happens immediately (don't wait a full interval to heal
  a stuck trade on startup).
- Subsequent reconciles happen at the configured interval.
- An exception in one reconcile doesn't kill the loop.
- Cancellation stops the loop promptly.
- End-to-end: a stuck OPENING trade that the exchange reports as FILLED
  gets healed on the next tick.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor, OrderReconciler, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.domain import TradeState
from ascent.exchanges.base import OrderStatusResponse
from tests.fakes import (
    FakeClock,
    FakeExchange,
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _wiring():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow = FakeUnitOfWorkFactory()
    processor = FillProcessor(
        trade_repo=trade_repo, order_repo=order_repo, event_bus=bus, uow_factory=uow
    )
    reconciler = OrderReconciler(
        order_repo=order_repo, fill_processor=processor, uow_factory=uow, trade_repo=trade_repo
    )
    return trade_repo, order_repo, bus, outbox, uow, processor, reconciler


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.002)
    raise AssertionError(f"predicate stayed falsy for {timeout}s")


class _CountingReconciler:
    """Records each reconcile call. Optionally raises for the first N calls."""

    def __init__(self, *, raise_times: int = 0) -> None:
        self.calls: list[tuple[object, uuid.UUID, datetime]] = []
        self._remaining_failures = raise_times

    async def reconcile(self, *, exchange, exchange_id, now) -> int:
        self.calls.append((exchange, exchange_id, now))
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated reconciler failure")
        return 0


class TestSchedulingBehavior:
    @pytest.mark.asyncio
    async def test_reconcile_runs_at_least_twice_over_interval(self):
        from ascent.application.reconciliation_service import PeriodicReconciliationService

        reconciler = _CountingReconciler()
        exchange = FakeExchange()
        service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=exchange,
            exchange_id=uuid.uuid4(),
            clock=FakeClock(NOW),
            interval_seconds=0.02,
        )

        task = asyncio.create_task(service.run_forever())
        try:
            await _wait_until(lambda: len(reconciler.calls) >= 3, timeout=1.0)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_first_reconcile_runs_immediately(self):
        """Don't make startup wait a full interval to heal anything stuck."""
        from ascent.application.reconciliation_service import PeriodicReconciliationService

        reconciler = _CountingReconciler()
        service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=FakeExchange(),
            exchange_id=uuid.uuid4(),
            clock=FakeClock(NOW),
            # Large interval so the test would hang if the first tick waited.
            interval_seconds=60.0,
        )

        task = asyncio.create_task(service.run_forever())
        try:
            await _wait_until(lambda: len(reconciler.calls) >= 1, timeout=0.5)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_reconciler_exception_does_not_stop_loop(self):
        from ascent.application.reconciliation_service import PeriodicReconciliationService

        reconciler = _CountingReconciler(raise_times=1)
        service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=FakeExchange(),
            exchange_id=uuid.uuid4(),
            clock=FakeClock(NOW),
            interval_seconds=0.02,
        )

        task = asyncio.create_task(service.run_forever())
        try:
            # Even though the first call raised, subsequent calls must happen.
            await _wait_until(lambda: len(reconciler.calls) >= 3, timeout=1.0)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cancellation_stops_loop_promptly(self):
        from ascent.application.reconciliation_service import PeriodicReconciliationService

        reconciler = _CountingReconciler()
        service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=FakeExchange(),
            exchange_id=uuid.uuid4(),
            clock=FakeClock(NOW),
            interval_seconds=5.0,
        )

        task = asyncio.create_task(service.run_forever())
        await _wait_until(lambda: len(reconciler.calls) >= 1, timeout=0.5)
        task.cancel()
        # Must honour cancellation without waiting out the full 5s interval.
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.5)


class TestStuckTradeHealing:
    """End-to-end: a stuck OPENING trade is healed on the next reconciler tick."""

    @pytest.mark.asyncio
    async def test_stuck_opening_trade_is_healed_on_next_tick(self):
        from ascent.application.reconciliation_service import PeriodicReconciliationService

        trade_repo, order_repo, bus, outbox, uow, _, reconciler = _wiring()
        exchange_id = uuid.uuid4()
        router = TradeRouter(
            strategy_id=uuid.uuid4(),
            portfolio_id=uuid.uuid4(),
            trade_repo=trade_repo,
            order_repo=order_repo,
            event_bus=bus,
            outbox=outbox,
            uow_factory=uow,
            exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
            is_paper=True,
        )
        draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
        entry_order = (await trade_repo.get(None, draft.trade_id)).legs[0].entry_order
        await order_repo.set_external_id(None, entry_order.id, "EX-STUCK-1")

        # Trade is OPENING but the exchange has actually FILLED the order —
        # simulate a dropped fill event. The reconciler should detect this.
        exchange = FakeExchange()
        exchange.open_orders.append(
            OrderStatusResponse(
                exchange_order_id="EX-STUCK-1",
                status="FILLED",
                filled_quantity=1.0,
                average_fill_price=100.0,
            )
        )

        service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=exchange,
            exchange_id=exchange_id,
            clock=FakeClock(NOW),
            interval_seconds=0.02,
        )

        task = asyncio.create_task(service.run_forever())
        try:
            await _wait_until(
                lambda: (
                    trade_repo._trades.get(draft.trade_id) is not None
                    and trade_repo._trades[draft.trade_id].state == TradeState.OPEN
                ),
                timeout=1.0,
            )
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
