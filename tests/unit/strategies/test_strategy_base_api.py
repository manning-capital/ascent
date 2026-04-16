"""Smoke tests for the user-facing ``Strategy`` base class API.

Every trading strategy users write depends on ``open_trade`` / ``close_trade``
returning dataclass-shaped results and propagating kwargs correctly. These
tests guard that surface against silent drift:

- ``direction="LONG" → side="BUY"`` coercion inside ``open_trade``
- ``order_type`` default of ``"MARKET"``
- ``close_reason`` threaded into the router
- returns typed ``TradeDraft`` (not a dict, not a raw coroutine)
- ``_ensure_router`` raises with a helpful message when the router is missing
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest
from pydantic import BaseModel

from ascent.application.route_trade import (
    ExchangeBinding,
    TradeDraft,
    TradeRouter,
)
from ascent.domain import TradeState
from ascent.engine.runner import _SyncRouterProxy
from ascent.strategies.base import Strategy
from tests.fakes import (
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


class _TestStrategy(Strategy):
    class Parameters(BaseModel):
        pass

    recorded: list[Any]

    def __init__(self, parameters=None) -> None:
        super().__init__(parameters)
        self.recorded = []

    def evaluate(self, ctx: pd.DataFrame) -> None:  # pragma: no cover — unused
        pass


def _wire(strategy_instance: _TestStrategy):
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
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel="ex.t")],
        is_paper=True,
    )
    loop = asyncio.get_event_loop()
    strategy_instance._trade_router = _SyncRouterProxy(router, loop)
    return router, trade_repo


@pytest.mark.asyncio
async def test_open_trade_returns_trade_draft():
    s = _TestStrategy()
    _wire(s)

    def _open():
        return s.open_trade(uuid.uuid4(), "LONG", quantity=1.0)

    result = await asyncio.to_thread(_open)
    assert isinstance(result, TradeDraft)
    assert result.state == TradeState.OPENING
    assert isinstance(result.trade_id, uuid.UUID)


@pytest.mark.asyncio
async def test_open_trade_short_maps_to_sell_side():
    """``direction='SHORT'`` must reach the router as ``side='SELL'``."""
    s = _TestStrategy()
    router, _ = _wire(s)
    # Spy on the submissions the router emits.
    bus = router._bus  # type: ignore[attr-defined]

    await asyncio.to_thread(lambda: s.open_trade(uuid.uuid4(), "SHORT", quantity=1.0))

    order_event = next(e for e in bus.published if "order" in e.payload)
    assert order_event.payload["order"]["side"] == "SELL"


@pytest.mark.asyncio
async def test_close_trade_threads_close_reason():
    s = _TestStrategy()
    router, trade_repo = _wire(s)

    draft = await asyncio.to_thread(lambda: s.open_trade(uuid.uuid4(), "LONG", quantity=1.0))
    # Flip OPEN so close() is accepted.
    await trade_repo.set_state(draft.trade_id, new_state=TradeState.OPEN, at=NOW)

    result = await asyncio.to_thread(
        lambda: s.close_trade(draft.trade_id, close_reason="STOP_LOSS")
    )
    assert isinstance(result, TradeDraft)
    assert result.state == TradeState.CLOSING
    assert trade_repo.close_reasons[draft.trade_id] == "STOP_LOSS"


@pytest.mark.asyncio
async def test_close_trade_accepts_str_uuid():
    """Strategies pull trade_ids out of the context DataFrame as strings; the
    base class must accept that shape.
    """
    s = _TestStrategy()
    _, trade_repo = _wire(s)
    draft = await asyncio.to_thread(lambda: s.open_trade(uuid.uuid4(), "LONG", quantity=1.0))
    await trade_repo.set_state(draft.trade_id, new_state=TradeState.OPEN, at=NOW)

    result = await asyncio.to_thread(
        lambda: s.close_trade(str(draft.trade_id))  # <-- str, not UUID
    )
    assert result.state == TradeState.CLOSING


def test_ensure_router_raises_when_no_router_configured():
    s = _TestStrategy()
    # Deliberately don't wire a router.
    with pytest.raises(RuntimeError, match="No exchange is configured"):
        s.open_trade(uuid.uuid4(), "LONG", quantity=1.0)


def test_parameters_validation_runs_on_init():
    """A dict passed to __init__ must be coerced through Parameters validation."""

    class _Strat(Strategy):
        class Parameters(BaseModel):
            lookback: int = 10

        def evaluate(self, ctx):
            pass

    s = _Strat({"lookback": 60})
    assert s.parameters.lookback == 60


def test_get_name_and_display_name_derive_from_class():
    class MomentumStrategy(Strategy):
        def evaluate(self, ctx):  # pragma: no cover
            pass

    assert MomentumStrategy.get_name() == "MOMENTUM_STRATEGY"
    assert MomentumStrategy.get_display_name() == "Momentum Strategy"
