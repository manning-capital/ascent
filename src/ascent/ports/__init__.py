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
from ascent.ports.outbox import OutboxPublisher
from ascent.ports.route_gate import RouteGate
from ascent.ports.run_tracker import RunTrackerPort
from ascent.ports.state_store import StateStore
from ascent.ports.strategy_universe import StrategyUniverseRepository
from ascent.ports.trade_repo import (
    FeedRunRepository,
    OrderRepository,
    PartitionRepository,
    StrategyRunRepository,
    TradeRepository,
)
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
    "LatestFeedStore",
    "OrderRepository",
    "OutboxPublisher",
    "PartitionRepository",
    "RouteGate",
    "RunTrackerPort",
    "StateStore",
    "StrategyRunRepository",
    "StrategyUniverseRepository",
    "TradeRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
