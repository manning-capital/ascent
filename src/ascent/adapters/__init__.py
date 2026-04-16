"""Ascent adapters — concrete implementations of :mod:`ascent.ports`.

Each adapter is independently importable so the Runner's composition
root can pick Redis + Timescale + asyncio in prod, or fakes in tests.
"""

from ascent.adapters.composite_feed_store import CompositeFeedStore
from ascent.adapters.exchange_wrapper import ExchangeAdapter
from ascent.adapters.redis_asyncio import (
    RedisEventBus,
    RedisFeedCache,
    RedisHeartbeat,
    RedisStateStore,
)
from ascent.adapters.sqlalchemy.feed_run_repo import SqlAlchemyFeedRunRepository
from ascent.adapters.sqlalchemy.mappers import OrmMappers
from ascent.adapters.sqlalchemy.order_repo import SqlAlchemyOrderRepository
from ascent.adapters.sqlalchemy.partition_repo import SqlAlchemyPartitionRepository
from ascent.adapters.sqlalchemy.run_tracker import SqlAlchemyRunTracker
from ascent.adapters.sqlalchemy.strategy_run_repo import SqlAlchemyStrategyRunRepository
from ascent.adapters.sqlalchemy.trade_repo import SqlAlchemyTradeRepository
from ascent.adapters.sqlalchemy.type_cache import TypeCache
from ascent.adapters.system_clock import SystemClock
from ascent.adapters.timescale_feed_store import TimescaleFeedStore

__all__ = [
    "CompositeFeedStore",
    "ExchangeAdapter",
    "OrmMappers",
    "RedisEventBus",
    "RedisFeedCache",
    "RedisHeartbeat",
    "RedisStateStore",
    "SqlAlchemyFeedRunRepository",
    "SqlAlchemyOrderRepository",
    "SqlAlchemyPartitionRepository",
    "SqlAlchemyRunTracker",
    "SqlAlchemyStrategyRunRepository",
    "SqlAlchemyTradeRepository",
    "SystemClock",
    "TimescaleFeedStore",
    "TypeCache",
]
