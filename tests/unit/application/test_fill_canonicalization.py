"""Tests for fill-event canonicalization in :class:`FillProcessor`.

These tests pin down a rule: **trust the numbers over the label**. When an
exchange reports ``PARTIALLY_FILLED`` but the ``filled_quantity`` already
covers the ordered quantity (within a tiny float-tolerance epsilon), the
order IS filled — promote the event to ``FILLED`` before handing it to
the domain state machine.

Motivation: the sim exchange (and some real exchanges) re-sum fill slices
with floats, landing on ``0.009999999999999998`` for an ordered quantity
of ``0.01``. Without canonicalization, trades stick in ``OPENING`` /
``CLOSING`` forever because the state machine only transitions on FILLED.

Canonicalization lives at the application-layer seam (``FillProcessor``),
NOT in the domain state machine — the state machine should stay pure and
literal. The boundary is where we normalize external reports.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ascent.application import FillProcessor
from ascent.domain import (
    FillEvent,
    Order,
    OrderSide,
    OrderState,
    PositionType,
    Trade,
    TradeLeg,
    TradeState,
)
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _wiring() -> tuple[
    FillProcessor, InMemoryTradeRepository, InMemoryOrderRepository, InMemoryEventBus
]:
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=FakeUnitOfWorkFactory(),
    )
    return processor, trade_repo, order_repo, bus


def _seed_opening_trade(
    trade_repo: InMemoryTradeRepository,
    order_repo: InMemoryOrderRepository,
    *,
    quantity: float = 0.01,
) -> tuple[Trade, Order]:
    entry = Order(
        id=uuid.uuid4(),
        state=OrderState.SUBMITTED,
        side=OrderSide.BUY,
        instrument_id=uuid.uuid4(),
        quantity=quantity,
        price=100.0,
    )
    leg = TradeLeg(
        id=uuid.uuid4(),
        instrument_id=entry.instrument_id,
        direction=PositionType.LONG,
        quantity=quantity,
        entry_order=entry,
    )
    trade = Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        state=TradeState.OPENING,
        is_paper=True,
        legs=(leg,),
        entry_at=NOW,
    )
    trade_repo.add(trade)
    order_repo.add(entry, trade_id=trade.id, leg_id=leg.id, exchange_id=uuid.uuid4())
    return trade, entry


def _seed_closing_trade(
    trade_repo: InMemoryTradeRepository,
    order_repo: InMemoryOrderRepository,
    *,
    quantity: float = 0.01,
) -> tuple[Trade, Order]:
    entry = Order(
        id=uuid.uuid4(),
        state=OrderState.FILLED,
        side=OrderSide.BUY,
        instrument_id=uuid.uuid4(),
        quantity=quantity,
        price=100.0,
        filled_quantity=quantity,
        average_fill_price=100.0,
    )
    exit_ = Order(
        id=uuid.uuid4(),
        state=OrderState.SUBMITTED,
        side=OrderSide.SELL,
        instrument_id=entry.instrument_id,
        quantity=quantity,
        price=110.0,
    )
    leg = TradeLeg(
        id=uuid.uuid4(),
        instrument_id=entry.instrument_id,
        direction=PositionType.LONG,
        quantity=quantity,
        entry_order=entry,
        exit_order=exit_,
        entry_price=100.0,
    )
    trade = Trade(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        state=TradeState.CLOSING,
        is_paper=True,
        legs=(leg,),
        entry_at=NOW,
    )
    trade_repo.add(trade)
    ex_id = uuid.uuid4()
    order_repo.add(entry, trade_id=trade.id, leg_id=leg.id, exchange_id=ex_id)
    order_repo.add(exit_, trade_id=trade.id, leg_id=leg.id, exchange_id=ex_id)
    return trade, exit_


# ---------------------------------------------------------------------------
# The bug we're fixing
# ---------------------------------------------------------------------------


class TestFloatDriftPromotion:
    @pytest.mark.asyncio
    async def test_partially_filled_with_near_full_quantity_promotes_to_open(self):
        """The exact production bug: PARTIALLY_FILLED + filled=0.0099999... on
        an order of 0.01 must promote to FILLED and transition the trade."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.009999999999999998,
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPEN, (
            f"Trade stuck in {reloaded.state}; canonicalization should have "
            "promoted 0.0099... (99.99% of 0.01) to FILLED."
        )
        reloaded_order = await order_repo.get(None, entry.id)
        assert reloaded_order.state == OrderState.FILLED
        # filled_quantity snapped to exact to avoid downstream PnL drift.
        assert reloaded_order.filled_quantity == 0.01

    @pytest.mark.asyncio
    async def test_closing_trade_with_partial_exit_drift_goes_closed(self):
        processor, trade_repo, order_repo, _ = _wiring()
        trade, exit_order = _seed_closing_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=exit_order.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.009999999999999998,
                average_fill_price=110.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.CLOSED


# ---------------------------------------------------------------------------
# Legitimate partial fills must NOT be promoted
# ---------------------------------------------------------------------------


class TestLegitimatePartialFillsStayPartial:
    @pytest.mark.asyncio
    async def test_half_filled_order_stays_partial(self):
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.005,
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPENING
        reloaded_order = await order_repo.get(None, entry.id)
        assert reloaded_order.state == OrderState.PARTIALLY_FILLED
        assert reloaded_order.filled_quantity == 0.005

    @pytest.mark.asyncio
    async def test_zero_filled_partial_stays_partial(self):
        """A PARTIALLY_FILLED report with filled=0 shouldn't happen but must
        not spuriously promote — fill quantity of 0 is clearly not filled."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPENING


# ---------------------------------------------------------------------------
# Overfill & epsilon boundary
# ---------------------------------------------------------------------------


class TestOverfillAndEpsilon:
    @pytest.mark.asyncio
    async def test_filled_quantity_greater_than_ordered_promotes_to_filled(self):
        """Trust the numbers: if the exchange says we got MORE than we
        asked for, the order is definitionally filled."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.01000000001,
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPEN
        reloaded_order = await order_repo.get(None, entry.id)
        assert reloaded_order.state == OrderState.FILLED
        # Snapped to ordered quantity, not the overfilled report.
        assert reloaded_order.filled_quantity == 0.01

    @pytest.mark.asyncio
    async def test_promotion_at_epsilon_boundary(self):
        """filled == ordered - 1e-9 → promote (inside tolerance)."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=1.0)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=1.0 - 1e-10,  # comfortably inside epsilon
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPEN

    @pytest.mark.asyncio
    async def test_no_promotion_outside_epsilon_boundary(self):
        """filled outside the tolerance must stay partial. 1% short of
        the order is clearly not a float-drift artifact."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=1.0)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.99,
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPENING


# ---------------------------------------------------------------------------
# Non-PARTIALLY_FILLED states pass through unchanged
# ---------------------------------------------------------------------------


class TestNonPartialStatesPassThrough:
    @pytest.mark.asyncio
    async def test_filled_event_passes_through_unchanged(self):
        """A FILLED event from the exchange shouldn't be touched — it's
        already the canonical outcome."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.FILLED,
                filled_quantity=0.01,
                average_fill_price=100.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPEN

    @pytest.mark.asyncio
    async def test_rejected_with_partial_fill_does_not_promote(self):
        """REJECTED is a terminal label; we respect it even if the order
        happened to accumulate near-full fills before rejection."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.REJECTED,
                filled_quantity=0.009999999,
                error_message="insufficient funds",
            ),
            now=NOW,
        )

        reloaded_order = await order_repo.get(None, entry.id)
        assert reloaded_order.state == OrderState.REJECTED
        # The trade went CANCELLED because all entry orders are rejected.
        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.CANCELLED

    @pytest.mark.asyncio
    async def test_cancelled_with_partial_fill_does_not_promote(self):
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.CANCELLED,
                filled_quantity=0.009999999,
            ),
            now=NOW,
        )

        reloaded_order = await order_repo.get(None, entry.id)
        assert reloaded_order.state == OrderState.CANCELLED

    @pytest.mark.asyncio
    async def test_submitted_passes_through_unchanged(self):
        """SUBMITTED with filled=0 is the initial ack — nothing to canonicalize."""
        processor, trade_repo, order_repo, _ = _wiring()
        trade, entry = _seed_opening_trade(trade_repo, order_repo, quantity=0.01)

        await processor.process(
            trade_id=trade.id,
            event=FillEvent(
                order_id=entry.id,
                state=OrderState.SUBMITTED,
                filled_quantity=0.0,
            ),
            now=NOW,
        )

        reloaded = await trade_repo.get(None, trade.id)
        assert reloaded.state == TradeState.OPENING


# ---------------------------------------------------------------------------
# Unknown-order resilience
# ---------------------------------------------------------------------------


class TestUnknownOrder:
    @pytest.mark.asyncio
    async def test_unknown_trade_is_still_dropped_quietly(self):
        """Canonicalization happens after trade lookup — an unknown trade
        id short-circuits before we ever look for an order quantity."""
        processor, _, _, bus = _wiring()
        await processor.process(
            trade_id=uuid.uuid4(),
            event=FillEvent(
                order_id=uuid.uuid4(),
                state=OrderState.PARTIALLY_FILLED,
                filled_quantity=0.01,
            ),
            now=NOW,
        )
        assert bus.published == []
