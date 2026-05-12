"""Scenario-test fixtures.

A scenario wires :class:`TradeRouter` + :class:`FillProcessor` + fakes together
so every test drives a realistic narrative (submit → fill → close → fill) and
asserts the **final** state. Catches cross-module integration bugs the way a
contract test catches port drift.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from ascent.application import FillProcessor, TradeRouter
from ascent.application.route_trade import ExchangeBinding
from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryOrderRepository,
    InMemoryOutboxPublisher,
    InMemoryTradeRepository,
)


@dataclass
class Scenario:
    router: TradeRouter
    processor: FillProcessor
    trade_repo: InMemoryTradeRepository
    order_repo: InMemoryOrderRepository
    bus: InMemoryEventBus
    outbox: InMemoryOutboxPublisher
    uow_factory: FakeUnitOfWorkFactory
    exchange_id: uuid.UUID
    strategy_id: uuid.UUID


@pytest.fixture
def scenario() -> Scenario:
    trade_repo = InMemoryTradeRepository()
    order_repo = InMemoryOrderRepository()
    trade_repo.link_order_repo(order_repo)
    order_repo.link_trade_repo(trade_repo)
    bus = InMemoryEventBus()
    outbox = InMemoryOutboxPublisher()
    uow_factory = FakeUnitOfWorkFactory()
    exchange_id = uuid.uuid4()
    strategy_id = uuid.uuid4()
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
    return Scenario(
        router=router,
        processor=processor,
        trade_repo=trade_repo,
        order_repo=order_repo,
        bus=bus,
        outbox=outbox,
        uow_factory=uow_factory,
        exchange_id=exchange_id,
        strategy_id=strategy_id,
    )
