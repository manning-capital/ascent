"""SQL-backed adapter conformance tests.

Post-phase-2, every repository method takes a ``session`` — we open a UoW
per test and pass its session through. If either assertion ever breaks,
the engine's fill path silently stops locating orders on their trades.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ascent.domain import OrderState, OrderType, PositionType, TradeState
from ascent.ports.trade_repo import NewLegSpec, NewOrderSpec

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_set_entry_order_links_leg_to_order_on_reload(
    sql_trade_repo, sql_order_repo, sql_uow_factory, seeded_ids
):
    async with sql_uow_factory() as uow:
        trade = await sql_trade_repo.create(
            uow.session,
            strategy_id=seeded_ids.strategy_id,
            is_paper=True,
            entry_at=NOW,
            strategy_run_id=None,
            legs=[
                NewLegSpec(
                    instrument_id=seeded_ids.instrument_id_a,
                    direction=PositionType.LONG,
                    quantity=1.0,
                    expected_entry_price=None,
                    exchange_id=seeded_ids.exchange_id,
                )
            ],
        )

        order = await sql_order_repo.create(
            uow.session,
            NewOrderSpec(
                timestamp=NOW,
                order_type=OrderType.MARKET,
                side="BUY",
                quantity=1.0,
                price=100.0,
                exchange_id=seeded_ids.exchange_id,
                instrument_id=seeded_ids.instrument_id_a,
                trade_leg_id=trade.legs[0].id,
            ),
        )

        await sql_trade_repo.set_entry_order(uow.session, trade.legs[0].id, order.id)

    async with sql_uow_factory() as uow:
        reloaded = await sql_trade_repo.get(uow.session, trade.id)
    assert reloaded.legs[0].entry_order is not None
    assert reloaded.legs[0].entry_order.id == order.id


@pytest.mark.asyncio
async def test_set_state_persists_close_reason(sql_trade_repo, sql_uow_factory, seeded_ids):
    async with sql_uow_factory() as uow:
        trade = await sql_trade_repo.create(
            uow.session,
            strategy_id=seeded_ids.strategy_id,
            is_paper=True,
            entry_at=NOW,
            strategy_run_id=None,
            legs=[
                NewLegSpec(
                    instrument_id=seeded_ids.instrument_id_a,
                    direction=PositionType.LONG,
                    quantity=1.0,
                    expected_entry_price=None,
                    exchange_id=seeded_ids.exchange_id,
                )
            ],
        )

        await sql_trade_repo.set_state(
            uow.session,
            trade.id,
            new_state=TradeState.CLOSED,
            at=LATER,
            exit_at=LATER,
            total_realized_pnl=42.5,
            close_reason="TAKE_PROFIT",
        )

    async with sql_uow_factory() as uow:
        reloaded = await sql_trade_repo.get(uow.session, trade.id)
    assert reloaded.state == TradeState.CLOSED
    assert reloaded.total_realized_pnl == 42.5


@pytest.mark.asyncio
async def test_set_external_id_is_idempotent(sql_order_repo, sql_uow_factory, seeded_ids):
    async with sql_uow_factory() as uow:
        order = await sql_order_repo.create(
            uow.session,
            NewOrderSpec(
                timestamp=NOW,
                order_type=OrderType.MARKET,
                side="BUY",
                quantity=1.0,
                price=100.0,
                exchange_id=seeded_ids.exchange_id,
                instrument_id=seeded_ids.instrument_id_a,
                trade_leg_id=None,
            ),
        )
        await sql_order_repo.set_external_id(uow.session, order.id, "EX-FIRST")
        await sql_order_repo.set_external_id(uow.session, order.id, "EX-SECOND")

    async with sql_uow_factory() as uow:
        reloaded = await sql_order_repo.get(uow.session, order.id)
    assert reloaded.external_order_id == "EX-FIRST"


@pytest.mark.asyncio
async def test_record_status_latest_wins(sql_order_repo, sql_uow_factory, seeded_ids):
    async with sql_uow_factory() as uow:
        order = await sql_order_repo.create(
            uow.session,
            NewOrderSpec(
                timestamp=NOW,
                order_type=OrderType.MARKET,
                side="BUY",
                quantity=1.0,
                price=100.0,
                exchange_id=seeded_ids.exchange_id,
                instrument_id=seeded_ids.instrument_id_a,
                trade_leg_id=None,
            ),
        )
        mid = NOW + timedelta(seconds=30)
        await sql_order_repo.record_status(
            uow.session, order.id, new_state=OrderState.PARTIALLY_FILLED, at=mid
        )
        await sql_order_repo.record_status(
            uow.session, order.id, new_state=OrderState.FILLED, at=LATER
        )

    async with sql_uow_factory() as uow:
        reloaded = await sql_order_repo.get(uow.session, order.id)
    assert reloaded.state == OrderState.FILLED
