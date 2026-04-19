"""Partial-fill and rejection scenarios."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.domain import FillEvent, OrderState, TradeState

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_partial_fill_keeps_trade_opening(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    order_id = trade.legs[0].entry_order.id

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=order_id,
            state=OrderState.PARTIALLY_FILLED,
            filled_quantity=0.4,
            average_fill_price=100.0,
        ),
        now=NOW,
    )
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.OPENING
    assert trade.legs[0].entry_price is None

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=order_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=100.5,
        ),
        now=NOW,
    )
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.OPEN
    assert trade.legs[0].entry_price == 100.5


@pytest.mark.asyncio
async def test_every_entry_rejected_cancels_trade(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    order_id = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order.id

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=order_id,
            state=OrderState.REJECTED,
            error_message="insufficient funds",
        ),
        now=NOW,
    )
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.CANCELLED


@pytest.mark.asyncio
async def test_exit_rejected_rolls_closing_back_to_open(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_id = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order.id

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=100.0,
        ),
        now=NOW,
    )
    assert (await scenario.trade_repo.get(None, draft.trade_id)).state == TradeState.OPEN

    await scenario.router.close(trade_id=draft.trade_id, now=NOW, close_reason="MODEL")
    exit_id = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].exit_order.id

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(order_id=exit_id, state=OrderState.REJECTED),
        now=NOW,
    )
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.OPEN
    assert trade.total_realized_pnl is None


@pytest.mark.asyncio
async def test_partial_exit_fill_keeps_trade_closing(scenario):
    draft = await scenario.router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
    entry_id = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].entry_order.id
    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=100.0,
        ),
        now=NOW,
    )
    await scenario.router.close(trade_id=draft.trade_id, now=NOW, close_reason="MODEL")
    exit_id = (await scenario.trade_repo.get(None, draft.trade_id)).legs[0].exit_order.id

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=exit_id,
            state=OrderState.PARTIALLY_FILLED,
            filled_quantity=0.6,
            average_fill_price=108.0,
        ),
        now=NOW,
    )
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    assert trade.state == TradeState.CLOSING
    assert trade.total_realized_pnl is None
