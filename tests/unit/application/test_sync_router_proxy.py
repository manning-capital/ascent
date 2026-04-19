"""Tests for the sync-from-thread router proxy."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application.route_trade import ExchangeBinding, TradeRouter
from ascent.domain import OrderType, TradeState
from ascent.engine.runner import _SyncRouterProxy
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _make_router():
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
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
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel="ascent.exchange.test")],
        is_paper=True,
    )
    return router, trade_repo, outbox


@pytest.mark.asyncio
async def test_proxy_submit_runs_from_worker_thread():
    router, trade_repo, _outbox = _make_router()
    loop = asyncio.get_running_loop()
    proxy = _SyncRouterProxy(router, loop)

    def _from_thread() -> dict:
        return proxy.submit(
            side="BUY",
            target_id=uuid.uuid4(),
            quantity=1.0,
            order_type="MARKET",
        )

    result = await asyncio.to_thread(_from_thread)
    assert result.state == TradeState.OPENING
    stored = await trade_repo.get(None, result.trade_id)
    assert stored.state == TradeState.OPENING


@pytest.mark.asyncio
async def test_proxy_close_from_worker_thread_with_close_reason():
    router, trade_repo, _outbox = _make_router()
    loop = asyncio.get_running_loop()
    proxy = _SyncRouterProxy(router, loop)

    def _open() -> dict:
        return proxy.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0)

    draft = await asyncio.to_thread(_open)
    await trade_repo.set_state(None, draft.trade_id, new_state=TradeState.OPEN, at=NOW)

    def _close():
        return proxy.close(trade_id=draft.trade_id, close_reason="STOP_LOSS")

    result = await asyncio.to_thread(_close)
    assert result.state == TradeState.CLOSING
    assert trade_repo.close_reasons[draft.trade_id] == "STOP_LOSS"


@pytest.mark.asyncio
async def test_proxy_returns_trade_draft_dataclass():
    from ascent.application.route_trade import TradeDraft

    router, trade_repo, _outbox = _make_router()
    proxy = _SyncRouterProxy(router, asyncio.get_running_loop())

    def _submit():
        return proxy.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0)

    result = await asyncio.to_thread(_submit)
    assert isinstance(result, TradeDraft)
    assert result.state == TradeState.OPENING
    assert isinstance(result.trade_id, uuid.UUID)
    assert isinstance(result.leg_summaries, list)

    await trade_repo.set_state(None, result.trade_id, new_state=TradeState.OPEN, at=NOW)

    def _close():
        return proxy.close(trade_id=result.trade_id)

    close_result = await asyncio.to_thread(_close)
    assert isinstance(close_result, TradeDraft)
    assert close_result.state == TradeState.CLOSING


@pytest.mark.asyncio
async def test_proxy_coerces_string_order_type_enum():
    router, _, outbox = _make_router()
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
    dispatch = outbox.enqueued[0]
    assert dispatch.payload["order"]["order_type"] == OrderType.LIMIT.value
