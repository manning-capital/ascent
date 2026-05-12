"""Ascent ports — async Protocols that describe what the engine *needs*.

Adapters live one layer out (``ascent.adapters``) and implement these.
Use cases (``ascent.application``) depend only on these Protocols, never
on concrete adapter classes.
"""

from ascent.ports.clock import Clock
from ascent.ports.durable_consumer import DurableConsumer, DurableMessage
from ascent.ports.durable_publisher import DurablePublisher
from ascent.ports.event_bus import Event, EventBus
from ascent.ports.exchange_port import ExchangePort
from ascent.ports.feed_store import FeedStore, HistoricalFeedStore, LatestFeedStore
from ascent.ports.heartbeat import HeartbeatStore
from ascent.ports.holdings_repo import HoldingsRepository
from ascent.ports.instrument_repo import InstrumentAssetIds, InstrumentRepository
from ascent.ports.outbox import OutboxPublisher
from ascent.ports.route_gate import RouteGate
from ascent.ports.run_tracker import RunTrackerPort
from ascent.ports.scope_repository import ScopeMembershipRecord, ScopeRepository
from ascent.ports.state_store import StateStore
from ascent.ports.strategy_universe import StrategyUniverseRepository
from ascent.ports.trade_repo import (
    FeedRunRepository,
    OrderRepository,
    StrategyRunRepository,
    TradeRepository,
)
from ascent.ports.transaction_repo import NewTransactionSpec, TransactionRepository
from ascent.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "Clock",
    "DurableConsumer",
    "DurableMessage",
    "DurablePublisher",
    "Event",
    "EventBus",
    "ExchangePort",
    "FeedRunRepository",
    "FeedStore",
    "HeartbeatStore",
    "HistoricalFeedStore",
    "HoldingsRepository",
    "InstrumentAssetIds",
    "InstrumentRepository",
    "LatestFeedStore",
    "NewTransactionSpec",
    "OrderRepository",
    "OutboxPublisher",
    "RouteGate",
    "RunTrackerPort",
    "ScopeMembershipRecord",
    "ScopeRepository",
    "StateStore",
    "StrategyRunRepository",
    "StrategyUniverseRepository",
    "TradeRepository",
    "TransactionRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
