"""Tests for the sync-from-thread router proxy.

Regression coverage for two bugs:

1. The proxy previously looked up the event loop via
   ``asyncio.get_event_loop_policy().get_event_loop()`` from inside a worker
   thread, which raises ``RuntimeError: There is no current event loop in
   thread ...`` on Python 3.12. Fix: capture the main loop at construction.

2. User strategies pass ``order_type="MARKET"`` as a string. The async router
   expects an ``OrderType`` enum; the proxy must coerce.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application.route_trade import ExchangeBinding, TradeRouter
from ascent.domain import OrderType, TradeState
from ascent.engine.runner import _SyncRouterProxy
from tests.fakes import (
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _make_router():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    exchange_id = uuid.uuid4()
    router = TradeRouter(
        strategy_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel="ascent.exchange.test")],
        is_paper=True,
    )
    return router, trade_repo


@pytest.mark.asyncio
async def test_proxy_submit_runs_from_worker_thread():
    """Proxy call from a worker thread must succeed — this is what user
    strategies do inside ``evaluate()`` via ``asyncio.to_thread``.
    """
    router, trade_repo = _make_router()
    loop = asyncio.get_running_loop()
    proxy = _SyncRouterProxy(router, loop)

    # The real breakage is: call the proxy from a thread that has no event loop.
    def _from_thread() -> dict:
        return proxy.submit(
            side="BUY",
            target_id=uuid.uuid4(),
            quantity=1.0,
            order_type="MARKET",  # string — previously the proxy didn't coerce
        )

    result = await asyncio.to_thread(_from_thread)
    assert result.state == TradeState.OPENING
    stored = await trade_repo.get(result.trade_id)
    assert stored.state == TradeState.OPENING


@pytest.mark.asyncio
async def test_proxy_close_from_worker_thread_with_close_reason():
    router, trade_repo = _make_router()
    loop = asyncio.get_running_loop()
    proxy = _SyncRouterProxy(router, loop)

    def _open() -> dict:
        return proxy.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0)

    draft = await asyncio.to_thread(_open)
    # Flip to OPEN so the router will accept a close.
    await trade_repo.set_state(draft.trade_id, new_state=TradeState.OPEN, at=NOW)

    def _close():
        return proxy.close(trade_id=draft.trade_id, close_reason="STOP_LOSS")

    result = await asyncio.to_thread(_close)
    assert result.state == TradeState.CLOSING
    assert trade_repo.close_reasons[draft.trade_id] == "STOP_LOSS"


@pytest.mark.asyncio
async def test_proxy_returns_trade_draft_dataclass():
    """Contract: proxy returns a ``TradeDraft`` — user code uses attribute access
    (``result.state``, ``result.trade_id``) not dict subscripting.
    """
    from ascent.application.route_trade import TradeDraft

    router, trade_repo = _make_router()
    proxy = _SyncRouterProxy(router, asyncio.get_running_loop())

    def _submit():
        return proxy.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0)

    result = await asyncio.to_thread(_submit)
    assert isinstance(result, TradeDraft)
    # Exact shape user code depends on:
    assert result.state == TradeState.OPENING
    assert isinstance(result.trade_id, uuid.UUID)
    assert isinstance(result.leg_summaries, list)

    # And for close():
    await trade_repo.set_state(result.trade_id, new_state=TradeState.OPEN, at=NOW)

    def _close():
        return proxy.close(trade_id=result.trade_id)

    close_result = await asyncio.to_thread(_close)
    assert isinstance(close_result, TradeDraft)
    assert close_result.state == TradeState.CLOSING


@pytest.mark.asyncio
async def test_proxy_coerces_string_order_type_enum():
    """The proxy normalizes ``order_type`` string → enum before calling the router."""
    router, _ = _make_router()
    proxy = _SyncRouterProxy(router, asyncio.get_running_loop())

    def _submit():
        return proxy.submit(
            side="SELL",
            target_id=uuid.uuid4(),
            quantity=1.5,
            order_type="LIMIT",
            price=99.0,
        )

    draft = await asyncio.to_thread(_submit)
    assert draft.state == TradeState.OPENING
    # Verify the coercion actually worked by checking the published order message.
    order_event = next(
        e
        for e in router._bus.published
        if "order" in e.payload  # type: ignore[attr-defined]
    )
    assert order_event.payload["order"]["order_type"] == OrderType.LIMIT.value
