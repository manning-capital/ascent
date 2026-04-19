"""TradeRouter use-case tests with in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from ascent.application.route_trade import (
    CompositeSpec,
    ExchangeBinding,
    TradeRouter,
)
from ascent.domain import Direction, TradeState
from ascent.ports import RouteGate
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


class _RejectingRouteGate(RouteGate):
    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def validate_open(
        self,
        session: Any,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        instrument_ids: list[uuid.UUID],
    ) -> str | None:
        return self._reason


def _router(*, route_gate: RouteGate | None = None):
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
        exchanges=[
            ExchangeBinding(exchange_id=exchange_id, channel=f"ascent.exchange.{exchange_id}")
        ],
        route_gate=route_gate,
        is_paper=True,
    )
    return router, trade_repo, order_repo, bus, outbox, exchange_id


class TestSubmitInstrument:
    @pytest.mark.asyncio
    async def test_submit_creates_trade_leg_and_order(self):
        router, trade_repo, order_repo, bus, outbox, exchange_id = _router()
        instrument_id = uuid.uuid4()

        draft = await router.submit(
            side="BUY",
            target_id=instrument_id,
            quantity=2.0,
            now=NOW,
        )

        assert draft.state == TradeState.OPENING
        trade = await trade_repo.get(None, draft.trade_id)
        assert trade.state == TradeState.OPENING
        assert len(trade.legs) == 1
        assert trade.legs[0].instrument_id == instrument_id
        assert trade.legs[0].direction == Direction.LONG

        # Dispatch intent lives in the outbox (durable), not the event bus.
        assert len(outbox.enqueued) == 1
        dispatch = outbox.enqueued[0]
        assert dispatch.channel == f"ascent.exchange.{exchange_id}"
        assert dispatch.payload["action"] == "submit_order"

        # UI ping is best-effort on the event bus.
        ui_events = [e for e in bus.published if e.channel == "ascent.trades.updates"]
        assert len(ui_events) == 1
        assert ui_events[0].payload == {
            "event": "trade_created",
            "trade_id": str(trade.id),
        }


class TestSubmitComposite:
    @pytest.mark.asyncio
    async def test_composite_first_leg_long_rest_short_on_buy(self):
        router, trade_repo, _, _, _, _ = _router()
        inst_a, inst_b, inst_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        comp_id = uuid.uuid4()
        draft = await router.submit(
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
        trade = await trade_repo.get(None, draft.trade_id)
        assert [leg.direction for leg in trade.legs] == [
            Direction.LONG,
            Direction.SHORT,
            Direction.SHORT,
        ]

    @pytest.mark.asyncio
    async def test_multi_leg_published_order_quantities_match_specs(self):
        router, _, _, bus, outbox, exchange_id = _router()
        inst_a, inst_b = uuid.uuid4(), uuid.uuid4()
        comp_id = uuid.uuid4()
        await router.submit(
            side="BUY",
            target_id=comp_id,
            scope="composite",
            quantity=2.5,
            now=NOW,
            composite=CompositeSpec(
                composite_id=comp_id,
                ordered_instrument_ids=[inst_a, inst_b],
            ),
        )
        dispatches = [e for e in outbox.enqueued if e.channel == f"ascent.exchange.{exchange_id}"]
        assert len(dispatches) == 2
        for entry in dispatches:
            payload = entry.payload
            assert payload["order"]["quantity"] == 2.5
            assert payload["order"]["from_asset_symbol"] in (str(inst_a), str(inst_b))


class TestRejection:
    @pytest.mark.asyncio
    async def test_rejected_submit_persists_terminal_trade_with_reason(self):
        router, trade_repo, _, bus, outbox, _ = _router(
            route_gate=_RejectingRouteGate("provider_mismatch")
        )
        instrument_id = uuid.uuid4()

        draft = await router.submit(
            side="BUY",
            target_id=instrument_id,
            quantity=1.0,
            now=NOW,
        )

        assert draft.state == TradeState.REJECTED
        assert draft.leg_summaries == []

        trade = await trade_repo.get(None, draft.trade_id)
        assert trade.state == TradeState.REJECTED
        assert trade.legs == ()
        assert trade_repo.close_reasons[draft.trade_id] == "UNIVERSE_SCOPE:provider_mismatch"

        # No orders or outbox entries on rejection
        assert outbox.enqueued == []

        # UI ping carries the rejection reason
        ui_events = [e for e in bus.published if e.channel == "ascent.trades.updates"]
        assert len(ui_events) == 1
        assert ui_events[0].payload == {
            "event": "trade_rejected",
            "trade_id": str(draft.trade_id),
            "reason": "provider_mismatch",
        }

    @pytest.mark.asyncio
    async def test_rejected_composite_does_not_create_legs_or_orders(self):
        router, trade_repo, order_repo, _, outbox, _ = _router(
            route_gate=_RejectingRouteGate("strategy_paused")
        )
        comp_id = uuid.uuid4()
        inst_a, inst_b = uuid.uuid4(), uuid.uuid4()

        draft = await router.submit(
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

        assert draft.state == TradeState.REJECTED
        trade = await trade_repo.get(None, draft.trade_id)
        assert trade.state == TradeState.REJECTED
        assert trade.legs == ()
        assert trade_repo.close_reasons[draft.trade_id] == "UNIVERSE_SCOPE:strategy_paused"
        assert outbox.enqueued == []

    @pytest.mark.asyncio
    async def test_no_op_gate_default_lets_submit_through(self):
        # Constructed without an explicit route_gate — the always-allow default kicks in.
        router, _, _, _, outbox, _ = _router()
        draft = await router.submit(
            side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW
        )
        assert draft.state == TradeState.OPENING
        assert len(outbox.enqueued) == 1


class TestClose:
    @pytest.mark.asyncio
    async def test_close_requires_open_state(self):
        router, _, _, _, _, _ = _router()
        draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
        with pytest.raises(ValueError, match="not OPEN"):
            await router.close(trade_id=draft.trade_id, now=NOW)

    @pytest.mark.asyncio
    async def test_close_persists_close_reason(self):
        from ascent.domain import TradeState

        router, trade_repo, _, _, _, _ = _router()
        draft = await router.submit(side="BUY", target_id=uuid.uuid4(), quantity=1.0, now=NOW)
        await trade_repo.set_state(None, draft.trade_id, new_state=TradeState.OPEN, at=NOW)

        await router.close(trade_id=draft.trade_id, now=NOW, close_reason="TAKE_PROFIT")

        assert trade_repo.close_reasons[draft.trade_id] == "TAKE_PROFIT"
