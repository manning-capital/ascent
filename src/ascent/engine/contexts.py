"""Engine composition-root context objects.

Three frozen dataclasses organize the adapters and services the Runner wires
at startup; :class:`EngineContext` aggregates them plus the task-lifecycle
primitives (``shutdown``, ``loop``). These are *composition conveniences* —
individual application services still accept only the narrow dependencies
they need (Interface Segregation preserved).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ascent.adapters import (
        CompositeFeedStore,
        OrmMappers,
        TimescaleFeedStore,
        TypeCache,
    )
    from ascent.application import (
        FeedExecutor,
        FeedPersister,
        FillProcessor,
        OrderReconciler,
    )
    from ascent.application.outbox_relay import OutboxReader
    from ascent.engine.deployer import Deployment
    from ascent.engine.queries import FeedRecord, StrategyInfo
    from ascent.ports.clock import Clock
    from ascent.ports.durable_publisher import DurablePublisher
    from ascent.ports.event_bus import EventBus
    from ascent.ports.feed_store import LatestFeedStore
    from ascent.ports.heartbeat import HeartbeatStore
    from ascent.ports.outbox import OutboxPublisher
    from ascent.ports.route_gate import RouteGate
    from ascent.ports.run_tracker import RunTrackerPort
    from ascent.ports.strategy_universe import StrategyUniverseRepository
    from ascent.ports.trade_repo import (
        FeedRunRepository,
        OrderRepository,
        StrategyRunRepository,
        TradeRepository,
    )
    from ascent.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class PersistenceContext:
    """DB engine, session factory, and all SQLAlchemy-backed adapters."""

    engine: Any
    session_factory: Any
    type_cache: TypeCache
    mappers: OrmMappers
    trade_repo: TradeRepository
    order_repo: OrderRepository
    universe_repo: StrategyUniverseRepository
    route_gate: RouteGate
    uow_factory: UnitOfWorkFactory
    outbox_publisher: OutboxPublisher
    outbox_reader: OutboxReader
    feed_run_repo: FeedRunRepository
    strategy_run_repo: StrategyRunRepository
    run_tracker: RunTrackerPort
    historical: TimescaleFeedStore


@dataclass(frozen=True)
class MessagingContext:
    """Redis, NATS, and the pub/sub + durable-messaging adapters."""

    redis: Any
    nc: Any
    event_bus: EventBus
    feed_cache: LatestFeedStore
    feed_store: CompositeFeedStore
    heartbeat_store: HeartbeatStore
    durable_publisher: DurablePublisher


@dataclass(frozen=True)
class RuntimeContext:
    """Services and preloaded data derived from the persistence/messaging stacks."""

    clock: Clock
    executor: FeedExecutor
    fill_processor: FillProcessor
    reconciler: OrderReconciler
    persister: FeedPersister
    deployment: Deployment
    feed_records: dict[uuid.UUID, FeedRecord]
    strategy_info_by_id: dict[uuid.UUID, StrategyInfo]
    composite_members: dict[uuid.UUID, list[uuid.UUID]]


@dataclass(frozen=True)
class EngineContext:
    """Full engine wiring surface plus task-lifecycle primitives."""

    persistence: PersistenceContext
    messaging: MessagingContext
    runtime: RuntimeContext
    shutdown: asyncio.Event
    loop: asyncio.AbstractEventLoop
