"""Contract tests for :class:`ascent.ports.TradeRepository`.

Every assertion must hold for **every** implementation. Running these against
a new backend (SQLAlchemy, in the future) guarantees the fake isn't lying.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.domain import PositionType, TradeState
from ascent.ports.trade_repo import NewLegSpec

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 16, 13, 0, tzinfo=UTC)


def _leg_spec(exchange_id: uuid.UUID, direction: PositionType = PositionType.LONG) -> NewLegSpec:
    return NewLegSpec(
        instrument_id=uuid.uuid4(),
        direction=direction,
        quantity=1.0,
        expected_entry_price=100.0,
        exchange_id=exchange_id,
    )


class TestCreateAndGet:
    @pytest.mark.asyncio
    async def test_create_round_trips(self, trade_repo, session):
        strategy_id = uuid.uuid4()
        portfolio_id = uuid.uuid4()
        exchange_id = uuid.uuid4()
        trade = await trade_repo.create(
            session,
            strategy_id=strategy_id,
            is_paper=True,
            entry_at=NOW,
            strategy_run_id=None,
            legs=[_leg_spec(exchange_id)],
        )
        fetched = await trade_repo.get(session, trade.id)
        assert fetched is not None
        assert fetched.id == trade.id
        assert fetched.strategy_id == strategy_id
        assert fetched.portfolio_id == portfolio_id
        assert fetched.is_paper is True
        assert fetched.state == TradeState.PENDING
        assert len(fetched.legs) == 1
        assert fetched.legs[0].direction == PositionType.LONG
        assert fetched.legs[0].quantity == 1.0

    @pytest.mark.asyncio
    async def test_get_missing_trade_returns_none(self, trade_repo, session):
        assert await trade_repo.get(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_create_multi_leg_preserves_order(self, trade_repo, session):
        exchange_id = uuid.uuid4()
        inst_a, inst_b, inst_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        trade = await trade_repo.create(
            session,
            strategy_id=uuid.uuid4(),
            is_paper=False,
            entry_at=NOW,
            strategy_run_id=uuid.uuid4(),
            legs=[
                NewLegSpec(
                    instrument_id=inst_a,
                    direction=PositionType.LONG,
                    quantity=1.0,
                    expected_entry_price=None,
                    exchange_id=exchange_id,
                ),
                NewLegSpec(
                    instrument_id=inst_b,
                    direction=PositionType.SHORT,
                    quantity=2.0,
                    expected_entry_price=None,
                    exchange_id=exchange_id,
                ),
                NewLegSpec(
                    instrument_id=inst_c,
                    direction=PositionType.SHORT,
                    quantity=3.0,
                    expected_entry_price=None,
                    exchange_id=exchange_id,
                ),
            ],
        )
        fetched = await trade_repo.get(session, trade.id)
        assert [leg.instrument_id for leg in fetched.legs] == [inst_a, inst_b, inst_c]
        assert [leg.direction for leg in fetched.legs] == [
            PositionType.LONG,
            PositionType.SHORT,
            PositionType.SHORT,
        ]
        assert [leg.quantity for leg in fetched.legs] == [1.0, 2.0, 3.0]


class TestOrderLinking:
    @pytest.mark.asyncio
    async def test_set_entry_order_populates_leg_entry_order(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        order_id = uuid.uuid4()

        await trade_repo.set_entry_order(session, trade.legs[0].id, order_id)

        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].entry_order is not None
        assert reloaded.legs[0].entry_order.id == order_id

    @pytest.mark.asyncio
    async def test_set_exit_order_populates_leg_exit_order(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        order_id = uuid.uuid4()

        await trade_repo.set_exit_order(session, trade.legs[0].id, order_id)

        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].exit_order is not None
        assert reloaded.legs[0].exit_order.id == order_id

    @pytest.mark.asyncio
    async def test_entry_and_exit_coexist(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        entry_id, exit_id = uuid.uuid4(), uuid.uuid4()

        await trade_repo.set_entry_order(session, trade.legs[0].id, entry_id)
        await trade_repo.set_exit_order(session, trade.legs[0].id, exit_id)

        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].entry_order.id == entry_id
        assert reloaded.legs[0].exit_order.id == exit_id


class TestSetState:
    @pytest.mark.asyncio
    async def test_state_transition_reflected_on_get(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        await trade_repo.set_state(session, trade.id, new_state=TradeState.OPENING, at=NOW)
        assert (await trade_repo.get(session, trade.id)).state == TradeState.OPENING

    @pytest.mark.asyncio
    async def test_close_persists_exit_at_pnl_and_reason(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        await trade_repo.set_state(
            session,
            trade.id,
            new_state=TradeState.CLOSED,
            at=LATER,
            exit_at=LATER,
            total_realized_pnl=42.5,
            close_reason="TAKE_PROFIT",
        )
        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.state == TradeState.CLOSED
        assert reloaded.exit_at == LATER
        assert reloaded.total_realized_pnl == 42.5


class TestSetLegPrices:
    @pytest.mark.asyncio
    async def test_entry_price_persisted(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        await trade_repo.set_leg_prices(session, trade.legs[0].id, entry_price=101.25)
        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].entry_price == 101.25

    @pytest.mark.asyncio
    async def test_exit_price_and_pnl_persisted(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        await trade_repo.set_leg_prices(
            session, trade.legs[0].id, exit_price=110.0, realized_pnl=9.5
        )
        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].exit_price == 110.0
        assert reloaded.legs[0].realized_pnl == 9.5

    @pytest.mark.asyncio
    async def test_partial_update_preserves_other_prices(self, trade_repo, session):
        trade = await _make_pending(trade_repo, session)
        await trade_repo.set_leg_prices(session, trade.legs[0].id, entry_price=100.0)
        await trade_repo.set_leg_prices(session, trade.legs[0].id, exit_price=110.0)
        reloaded = await trade_repo.get(session, trade.id)
        assert reloaded.legs[0].entry_price == 100.0
        assert reloaded.legs[0].exit_price == 110.0


class TestListing:
    @pytest.mark.asyncio
    async def test_list_non_terminal_excludes_closed_and_cancelled(self, trade_repo, session):
        strategy_id = uuid.uuid4()
        active = await _make_pending(trade_repo, session, strategy_id=strategy_id)
        closed = await _make_pending(trade_repo, session, strategy_id=strategy_id)
        cancelled = await _make_pending(trade_repo, session, strategy_id=strategy_id)
        other = await _make_pending(trade_repo, session, strategy_id=uuid.uuid4())

        await trade_repo.set_state(session, closed.id, new_state=TradeState.CLOSED, at=NOW)
        await trade_repo.set_state(session, cancelled.id, new_state=TradeState.CANCELLED, at=NOW)
        await trade_repo.set_state(session, active.id, new_state=TradeState.OPEN, at=NOW)

        non_terminal = await trade_repo.list_non_terminal_for_strategy(session, strategy_id)
        ids = {t.id for t in non_terminal}
        assert active.id in ids
        assert closed.id not in ids
        assert cancelled.id not in ids
        assert other.id not in ids

    @pytest.mark.asyncio
    async def test_list_open_only_returns_open_state(self, trade_repo, session):
        strategy_id = uuid.uuid4()
        opening = await _make_pending(trade_repo, session, strategy_id=strategy_id)
        opened = await _make_pending(trade_repo, session, strategy_id=strategy_id)
        closing = await _make_pending(trade_repo, session, strategy_id=strategy_id)

        await trade_repo.set_state(session, opening.id, new_state=TradeState.OPENING, at=NOW)
        await trade_repo.set_state(session, opened.id, new_state=TradeState.OPEN, at=NOW)
        await trade_repo.set_state(session, closing.id, new_state=TradeState.CLOSING, at=NOW)

        open_trades = await trade_repo.list_open_for_strategy(session, strategy_id)
        assert {t.id for t in open_trades} == {opened.id}


async def _make_pending(trade_repo, session, *, strategy_id: uuid.UUID | None = None):
    return await trade_repo.create(
        session,
        strategy_id=strategy_id or uuid.uuid4(),
        is_paper=True,
        entry_at=NOW,
        strategy_run_id=None,
        legs=[_leg_spec(uuid.uuid4())],
    )
