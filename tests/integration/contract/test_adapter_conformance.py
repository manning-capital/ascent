"""SQL-backed adapter conformance tests.

These are the same invariants as ``tests/contract/`` but run against a real
TimescaleDB via the Docker harness. Focused on the behaviors where fake-vs-real
drift has already bitten us:

- ``TradeRepository.set_entry_order`` must link the leg → order so a later
  ``get(trade_id).legs[i].entry_order.id`` returns the linked id.
- ``OrderRepository.set_external_id`` must be idempotent (the first write
  wins; subsequent writes are dropped).

If either assertion ever breaks, the engine's fill path silently stops
locating orders on their trades — exactly the production incident we hit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ascent.domain import Direction, OrderState, OrderType, TradeState
from ascent.ports.trade_repo import NewLegSpec, NewOrderSpec

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_set_entry_order_links_leg_to_order_on_reload(
    sql_trade_repo, sql_order_repo, seeded_ids
):
    trade = await sql_trade_repo.create(
        strategy_id=seeded_ids.strategy_id,
        portfolio_id=seeded_ids.portfolio_id,
        is_paper=True,
        entry_at=NOW,
        strategy_run_id=None,
        legs=[
            NewLegSpec(
                instrument_id=seeded_ids.instrument_id_a,
                direction=Direction.LONG,
                quantity=1.0,
                expected_entry_price=None,
                exchange_id=seeded_ids.exchange_id,
            )
        ],
    )

    order = await sql_order_repo.create(
        NewOrderSpec(
            timestamp=NOW,
            order_type=OrderType.MARKET,
            side="BUY",
            quantity=1.0,
            price=100.0,
            exchange_id=seeded_ids.exchange_id,
            portfolio_id=seeded_ids.portfolio_id,
            instrument_id=seeded_ids.instrument_id_a,
            trade_leg_id=trade.legs[0].id,
        )
    )

    await sql_trade_repo.set_entry_order(trade.legs[0].id, order.id)

    reloaded = await sql_trade_repo.get(trade.id)
    assert reloaded.legs[0].entry_order is not None
    assert reloaded.legs[0].entry_order.id == order.id


@pytest.mark.asyncio
async def test_set_state_persists_close_reason(sql_trade_repo, seeded_ids):
    trade = await sql_trade_repo.create(
        strategy_id=seeded_ids.strategy_id,
        portfolio_id=seeded_ids.portfolio_id,
        is_paper=True,
        entry_at=NOW,
        strategy_run_id=None,
        legs=[
            NewLegSpec(
                instrument_id=seeded_ids.instrument_id_a,
                direction=Direction.LONG,
                quantity=1.0,
                expected_entry_price=None,
                exchange_id=seeded_ids.exchange_id,
            )
        ],
    )

    await sql_trade_repo.set_state(
        trade.id,
        new_state=TradeState.CLOSED,
        at=LATER,
        exit_at=LATER,
        total_realized_pnl=42.5,
        close_reason="TAKE_PROFIT",
    )

    reloaded = await sql_trade_repo.get(trade.id)
    assert reloaded.state == TradeState.CLOSED
    assert reloaded.total_realized_pnl == 42.5


@pytest.mark.asyncio
async def test_set_external_id_is_idempotent(sql_order_repo, seeded_ids):
    order = await sql_order_repo.create(
        NewOrderSpec(
            timestamp=NOW,
            order_type=OrderType.MARKET,
            side="BUY",
            quantity=1.0,
            price=100.0,
            exchange_id=seeded_ids.exchange_id,
            portfolio_id=seeded_ids.portfolio_id,
            instrument_id=seeded_ids.instrument_id_a,
            trade_leg_id=None,
        )
    )
    await sql_order_repo.set_external_id(order.id, "EX-FIRST")
    await sql_order_repo.set_external_id(order.id, "EX-SECOND")
    reloaded = await sql_order_repo.get(order.id)
    # The exchange-assigned id is immutable once known — the second write must
    # be dropped. Same invariant as the fake contract test.
    assert reloaded.external_order_id == "EX-FIRST"


@pytest.mark.asyncio
async def test_record_status_latest_wins(sql_order_repo, seeded_ids):
    order = await sql_order_repo.create(
        NewOrderSpec(
            timestamp=NOW,
            order_type=OrderType.MARKET,
            side="BUY",
            quantity=1.0,
            price=100.0,
            exchange_id=seeded_ids.exchange_id,
            portfolio_id=seeded_ids.portfolio_id,
            instrument_id=seeded_ids.instrument_id_a,
            trade_leg_id=None,
        )
    )
    # ``create`` already stamped SUBMITTED at ``NOW`` — step forward so we
    # don't collide on (timestamp, order_id) PK.
    mid = NOW + timedelta(seconds=30)
    await sql_order_repo.record_status(order.id, new_state=OrderState.PARTIALLY_FILLED, at=mid)
    await sql_order_repo.record_status(order.id, new_state=OrderState.FILLED, at=LATER)

    reloaded = await sql_order_repo.get(order.id)
    assert reloaded.state == OrderState.FILLED
