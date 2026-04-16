"""Ascent ports — async Protocols that describe what the engine *needs*.

Adapters live one layer out (``ascent.adapters``) and implement these.
Use cases (``ascent.application``) depend only on these Protocols, never
on concrete adapter classes.
"""

from ascent.ports.clock import Clock
from ascent.ports.event_bus import Event, EventBus
from ascent.ports.exchange_port import ExchangePort
from ascent.ports.feed_store import FeedStore, HistoricalFeedStore, LatestFeedStore
from ascent.ports.heartbeat import HeartbeatStore
from ascent.ports.run_tracker import RunTrackerPort
from ascent.ports.state_store import StateStore
from ascent.ports.trade_repo import (
    FeedRunRepository,
    OrderRepository,
    PartitionRepository,
    StrategyRunRepository,
    TradeRepository,
)

__all__ = [
    "Clock",
    "Event",
    "EventBus",
    "ExchangePort",
    "FeedRunRepository",
    "FeedStore",
    "HeartbeatStore",
    "HistoricalFeedStore",
    "LatestFeedStore",
    "OrderRepository",
    "PartitionRepository",
    "RunTrackerPort",
    "StateStore",
    "StrategyRunRepository",
    "TradeRepository",
]
