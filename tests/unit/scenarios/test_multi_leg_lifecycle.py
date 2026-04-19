"""Multi-leg (composite) trade lifecycle scenarios."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application.route_trade import CompositeSpec
from ascent.domain import FillEvent, OrderState, TradeState

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_composite_trade_opens_only_when_every_entry_fills(scenario):
    inst_a, inst_b, inst_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    comp_id = uuid.uuid4()

    draft = await scenario.router.submit(
        side="BUY",
        target_id=comp_id,
        scope="composite",
        quantity=1.0,
        now=NOW,
        composite=CompositeSpec(
            composite_id=comp_id,
            ordered_instrument_ids=[inst_a, inst_b, inst_c],
        ),
    )

    trade = await scenario.trade_repo.get(None, draft.trade_id)
    entry_ids = [leg.entry_order.id for leg in trade.legs]
    assert all(entry_ids), "every leg must be linked to its entry order"

    for i in (0, 2):
        await scenario.processor.process(
            trade_id=draft.trade_id,
            event=FillEvent(
                order_id=entry_ids[i],
                state=OrderState.FILLED,
                filled_quantity=1.0,
                average_fill_price=100.0 + i,
            ),
            now=NOW,
        )
        assert (await scenario.trade_repo.get(None, draft.trade_id)).state == TradeState.OPENING

    await scenario.processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_ids[1],
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=200.0,
        ),
        now=NOW,
    )
    opened = await scenario.trade_repo.get(None, draft.trade_id)
    assert opened.state == TradeState.OPEN
    assert [leg.entry_price for leg in opened.legs] == [100.0, 200.0, 102.0]


@pytest.mark.asyncio
async def test_composite_trade_close_aggregates_pnl_across_legs(scenario):
    inst_a, inst_b = uuid.uuid4(), uuid.uuid4()
    comp_id = uuid.uuid4()
    draft = await scenario.router.submit(
        side="BUY",
        target_id=comp_id,
        scope="composite",
        quantity=1.0,
        now=NOW,
        composite=CompositeSpec(
            composite_id=comp_id,
            ordered_instrument_ids=[inst_a, inst_b],
        ),
    )

    trade = await scenario.trade_repo.get(None, draft.trade_id)
    for leg, entry_price in zip(trade.legs, [100.0, 50.0], strict=True):
        await scenario.processor.process(
            trade_id=draft.trade_id,
            event=FillEvent(
                order_id=leg.entry_order.id,
                state=OrderState.FILLED,
                filled_quantity=1.0,
                average_fill_price=entry_price,
            ),
            now=NOW,
        )
    assert (await scenario.trade_repo.get(None, draft.trade_id)).state == TradeState.OPEN

    await scenario.router.close(trade_id=draft.trade_id, now=NOW, close_reason="MODEL")
    trade = await scenario.trade_repo.get(None, draft.trade_id)
    exit_ids = [leg.exit_order.id for leg in trade.legs]

    for exit_id, exit_price in zip(exit_ids, [110.0, 45.0], strict=True):
        await scenario.processor.process(
            trade_id=draft.trade_id,
            event=FillEvent(
                order_id=exit_id,
                state=OrderState.FILLED,
                filled_quantity=1.0,
                average_fill_price=exit_price,
            ),
            now=NOW,
        )

    final = await scenario.trade_repo.get(None, draft.trade_id)
    assert final.state == TradeState.CLOSED
    assert final.total_realized_pnl == 15.0
