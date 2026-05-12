"""FillProcessor double-entry — fills update Holdings + Transaction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ascent.application import FillProcessor, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from ascent.domain import FillEvent, OrderState, PositionType
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryHoldingsRepository,
    InMemoryInstrumentRepository,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
    InMemoryTransactionRepository,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def harness():
    """Wire a TradeRouter + FillProcessor with all double-entry repos."""
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    holdings = InMemoryHoldingsRepository()
    transactions = InMemoryTransactionRepository()
    instruments = InMemoryInstrumentRepository()
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow_factory = FakeUnitOfWorkFactory()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)

    exchange_id = uuid.uuid4()
    strategy_id = uuid.uuid4()
    instrument_id = uuid.uuid4()
    btc_id = uuid.uuid4()
    usd_id = uuid.uuid4()
    instruments.register(
        instrument_id,
        from_asset="BTC",
        to_asset="USD",
        from_asset_id=btc_id,
        to_asset_id=usd_id,
    )
    trade_repo.register_instrument_assets(instrument_id, "BTC", "USD")

    router = TradeRouter(
        strategy_id=strategy_id,
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
        is_paper=True,
        instrument_repo=instruments,
    )
    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
        holdings_repo=holdings,
        transactions_repo=transactions,
        instrument_repo=instruments,
    )
    return {
        "router": router,
        "processor": processor,
        "holdings": holdings,
        "transactions": transactions,
        "trade_repo": trade_repo,
        "exchange_id": exchange_id,
        "strategy_id": strategy_id,
        "instrument_id": instrument_id,
        "btc_id": btc_id,
        "usd_id": usd_id,
    }


async def _open_then_fill(h, *, side: str, quantity: float, price: float):
    draft = await h["router"].submit(
        side=side, target_id=h["instrument_id"], quantity=quantity, now=NOW
    )
    trade = await h["trade_repo"].get(None, draft.trade_id)
    entry_order = trade.legs[0].entry_order
    await h["processor"].process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_order.id,
            state=OrderState.FILLED,
            filled_quantity=quantity,
            average_fill_price=price,
        ),
        now=NOW,
    )
    return draft.trade_id


@pytest.mark.asyncio
async def test_long_entry_credits_long_holding(harness):
    """BUY entry → +qty on the LONG row, one BUY Transaction recorded."""
    await _open_then_fill(harness, side="BUY", quantity=1.0, price=50000.0)

    qty = harness["holdings"].quantity_for(
        strategy_id=harness["strategy_id"],
        exchange_id=harness["exchange_id"],
        asset_id=harness["btc_id"],
        position_type=PositionType.LONG,
    )
    assert qty == 1.0

    assert len(harness["transactions"].records) == 1
    _, spec = harness["transactions"].records[0]
    assert spec.transaction_type == "BUY"
    assert spec.from_asset_id == harness["usd_id"]
    assert spec.to_asset_id == harness["btc_id"]
    assert spec.quantity == 1.0
    assert spec.price == 50000.0
    assert spec.strategy_id == harness["strategy_id"]


@pytest.mark.asyncio
async def test_short_entry_credits_short_holding(harness):
    """SELL entry → +qty on the SHORT row, one SELL Transaction recorded."""
    await _open_then_fill(harness, side="SELL", quantity=0.5, price=60000.0)

    qty = harness["holdings"].quantity_for(
        strategy_id=harness["strategy_id"],
        exchange_id=harness["exchange_id"],
        asset_id=harness["btc_id"],
        position_type=PositionType.SHORT,
    )
    assert qty == 0.5

    _, spec = harness["transactions"].records[0]
    assert spec.transaction_type == "SELL"
    assert spec.from_asset_id == harness["btc_id"]
    assert spec.to_asset_id == harness["usd_id"]


@pytest.mark.asyncio
async def test_long_exit_drains_long_holding(harness):
    """A long round-trip nets to zero on the LONG row."""
    trade_id = await _open_then_fill(harness, side="BUY", quantity=1.0, price=50000.0)

    # Submit close orders, then fill.
    await harness["router"].close(trade_id=trade_id, now=NOW)
    trade = await harness["trade_repo"].get(None, trade_id)
    exit_order = trade.legs[0].exit_order
    await harness["processor"].process(
        trade_id=trade_id,
        event=FillEvent(
            order_id=exit_order.id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=51000.0,
        ),
        now=NOW,
    )

    qty = harness["holdings"].quantity_for(
        strategy_id=harness["strategy_id"],
        exchange_id=harness["exchange_id"],
        asset_id=harness["btc_id"],
        position_type=PositionType.LONG,
    )
    assert qty == 0.0
    assert len(harness["transactions"].records) == 2  # entry BUY + exit SELL


@pytest.mark.asyncio
async def test_double_entry_skipped_when_repos_unwired():
    """A FillProcessor without the optional repos still processes fills."""
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow_factory = FakeUnitOfWorkFactory()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)

    exchange_id = uuid.uuid4()
    strategy_id = uuid.uuid4()
    instrument_id = uuid.uuid4()
    trade_repo.register_instrument_assets(instrument_id, "BTC", "USD")
    router = TradeRouter(
        strategy_id=strategy_id,
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchanges=[ExchangeBinding(exchange_id=exchange_id, channel=f"ex.{exchange_id}")],
        is_paper=True,
    )
    processor = FillProcessor(
        trade_repo=trade_repo,
        order_repo=order_repo,
        event_bus=bus,
        uow_factory=uow_factory,
    )

    draft = await router.submit(side="BUY", target_id=instrument_id, quantity=1.0, now=NOW)
    trade = await trade_repo.get(None, draft.trade_id)
    entry_order = trade.legs[0].entry_order
    # Should not raise even though no holdings/transaction repos are wired.
    await processor.process(
        trade_id=draft.trade_id,
        event=FillEvent(
            order_id=entry_order.id,
            state=OrderState.FILLED,
            filled_quantity=1.0,
            average_fill_price=50000.0,
        ),
        now=NOW,
    )


@pytest.mark.asyncio
async def test_decimal_delta_precision(harness):
    """Quantity_delta preserves Decimal precision through the in-memory store."""
    await _open_then_fill(harness, side="BUY", quantity=0.123456789012, price=50000.0)
    qty = harness["holdings"].quantity_for(
        strategy_id=harness["strategy_id"],
        exchange_id=harness["exchange_id"],
        asset_id=harness["btc_id"],
        position_type=PositionType.LONG,
    )
    assert Decimal(str(qty)) == Decimal("0.123456789012")
