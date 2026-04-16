"""Contract tests for :class:`ascent.ports.OrderRepository`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.domain import OrderState, OrderType
from ascent.ports.trade_repo import NewOrderSpec

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 16, 12, 1, tzinfo=UTC)


def _spec(
    *,
    exchange_id: uuid.UUID | None = None,
    trade_leg_id: uuid.UUID | None = None,
    side: str = "BUY",
    quantity: float = 1.0,
) -> NewOrderSpec:
    return NewOrderSpec(
        timestamp=NOW,
        order_type=OrderType.MARKET,
        side=side,
        quantity=quantity,
        price=100.0,
        exchange_id=exchange_id or uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        trade_leg_id=trade_leg_id,
    )


class TestCreateAndGet:
    @pytest.mark.asyncio
    async def test_create_round_trips(self, order_repo):
        leg_id = uuid.uuid4()
        spec = _spec(trade_leg_id=leg_id, side="SELL", quantity=2.5)

        order = await order_repo.create(spec)

        fetched = await order_repo.get(order.id)
        assert fetched is not None
        assert fetched.id == order.id
        assert fetched.instrument_id == spec.instrument_id
        assert fetched.quantity == 2.5
        # New orders start SUBMITTED — this is part of the repo's contract, not
        # the caller's responsibility.
        assert fetched.state == OrderState.SUBMITTED

    @pytest.mark.asyncio
    async def test_get_missing_order_returns_none(self, order_repo):
        assert await order_repo.get(uuid.uuid4()) is None


class TestRecordStatus:
    @pytest.mark.asyncio
    async def test_latest_status_wins(self, order_repo):
        order = await order_repo.create(_spec())

        await order_repo.record_status(order.id, new_state=OrderState.PARTIALLY_FILLED, at=NOW)
        await order_repo.record_status(order.id, new_state=OrderState.FILLED, at=LATER)

        assert (await order_repo.get(order.id)).state == OrderState.FILLED

    @pytest.mark.asyncio
    async def test_rejection_carries_error_message(self, order_repo):
        order = await order_repo.create(_spec())
        await order_repo.record_status(
            order.id,
            new_state=OrderState.REJECTED,
            at=NOW,
            error_message="insufficient balance",
        )
        fetched = await order_repo.get(order.id)
        assert fetched.state == OrderState.REJECTED
        assert fetched.error_message == "insufficient balance"


class TestFillsAndExternalId:
    @pytest.mark.asyncio
    async def test_set_fill_updates_qty_and_avg_price(self, order_repo):
        order = await order_repo.create(_spec())
        await order_repo.set_fill(order.id, filled_quantity=0.75, average_fill_price=99.25)
        fetched = await order_repo.get(order.id)
        assert fetched.filled_quantity == 0.75
        assert fetched.average_fill_price == 99.25

    @pytest.mark.asyncio
    async def test_set_external_id_is_idempotent(self, order_repo):
        """A second ``set_external_id`` must not overwrite the first — the
        exchange-assigned id is immutable once known.
        """
        order = await order_repo.create(_spec())
        await order_repo.set_external_id(order.id, "EX-FIRST")
        await order_repo.set_external_id(order.id, "EX-SECOND")
        assert (await order_repo.get(order.id)).external_order_id == "EX-FIRST"


class TestListForExchange:
    @pytest.mark.asyncio
    async def test_returns_tuples_with_leg_and_trade_ids(self, order_repo):
        exchange_id = uuid.uuid4()
        leg_id = uuid.uuid4()
        order = await order_repo.create(_spec(exchange_id=exchange_id, trade_leg_id=leg_id))

        # In-memory repo requires the trade linkage to be stamped by the test;
        # real repos derive this via FK. We use the fake's ``add`` helper when
        # available; otherwise assume the FK path and supply a trade_id fixture.
        trade_id = uuid.uuid4()
        if hasattr(order_repo, "_trade_of"):
            order_repo._trade_of[order.id] = trade_id

        rows = await order_repo.list_for_exchange(exchange_id)
        assert any(
            returned_order.id == order.id
            and returned_leg_id == leg_id
            and returned_trade_id == trade_id
            for returned_order, returned_leg_id, returned_trade_id in rows
        )

    @pytest.mark.asyncio
    async def test_excludes_other_exchanges(self, order_repo):
        ours = uuid.uuid4()
        theirs = uuid.uuid4()
        ours_order = await order_repo.create(_spec(exchange_id=ours, trade_leg_id=uuid.uuid4()))
        theirs_order = await order_repo.create(_spec(exchange_id=theirs, trade_leg_id=uuid.uuid4()))
        if hasattr(order_repo, "_trade_of"):
            order_repo._trade_of[ours_order.id] = uuid.uuid4()
            order_repo._trade_of[theirs_order.id] = uuid.uuid4()

        returned = await order_repo.list_for_exchange(ours)
        returned_ids = {o.id for o, _, _ in returned}
        assert ours_order.id in returned_ids
        assert theirs_order.id not in returned_ids
