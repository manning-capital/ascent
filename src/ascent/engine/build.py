"""Infrastructure bring-up and adapter wiring.

Given a :class:`RunnerConfig`, connect to the database, Redis, and NATS,
provision the exchange stream, and construct every adapter in
:class:`PersistenceContext` and :class:`MessagingContext`. Teardown is
registered on an :class:`AsyncExitStack` so the Runner's ``finally`` becomes
``await stack.aclose()``.

Runtime-only artifacts (:class:`FeedExecutor`, :class:`FillProcessor`,
:class:`OrderReconciler`, :class:`FeedPersister`) plus preloaded records are
assembled by the Runner *after* deploy + startup queries complete and merged
into the final :class:`EngineContext`.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ascent.adapters import (
    CompositeFeedStore,
    OrmMappers,
    RedisEventBus,
    RedisFeedCache,
    RedisHeartbeat,
    RedisStateStore,
    SqlAlchemyFeedRunRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
    SqlAlchemyRouteGate,
    SqlAlchemyRunTracker,
    SqlAlchemyStrategyRunRepository,
    SqlAlchemyStrategyUniverseRepository,
    SqlAlchemyTradeRepository,
    SqlAlchemyUnitOfWorkFactory,
    TimescaleFeedStore,
    TypeCache,
)
from ascent.adapters.nats import NatsJetStreamPublisher, connect_nats, ensure_stream
from ascent.adapters.redis_asyncio import create_redis_client
from ascent.engine.contexts import MessagingContext, PersistenceContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    database_url: str
    redis_url: str
    nats_url: str


async def build_infra(
    cfg: RunnerConfig,
) -> tuple[PersistenceContext, MessagingContext, AsyncExitStack]:
    """Connect to infra + construct every adapter. Caller owns the ``AsyncExitStack``."""
    stack = AsyncExitStack()
    try:
        engine = create_engine(cfg.database_url)
        session_factory = sessionmaker(bind=engine)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to database at %s", cfg.database_url)

        redis = create_redis_client(cfg.redis_url)
        await redis.ping()
        logger.info("Connected to Redis at %s", cfg.redis_url)
        stack.push_async_callback(redis.aclose)

        nc = await connect_nats(cfg.nats_url, name="ascent-engine")
        logger.info("Connected to NATS at %s", cfg.nats_url)
        stack.push_async_callback(_safe_close_nats, nc)

        # Provision the dispatch + fill-response stream. Subject taxonomy:
        # - ascent.exchange.<exchange-id>            — dispatch
        # - ascent.exchange.<exchange-id>.responses  — fills
        # Both live on one stream; consumers use filter_subject to split.
        await ensure_stream(
            nc,
            stream_name="ASCENT_EXCHANGE",
            subjects=["ascent.exchange.>"],
        )

        persistence = _build_persistence(engine, session_factory)
        messaging = _build_messaging(redis, nc, persistence.historical)
    except BaseException:
        await stack.aclose()
        raise

    return persistence, messaging, stack


def _build_persistence(engine, session_factory) -> PersistenceContext:
    type_cache = TypeCache(session_factory)
    mappers = OrmMappers(type_cache)
    feed_run_repo = SqlAlchemyFeedRunRepository(session_factory)
    strategy_run_repo = SqlAlchemyStrategyRunRepository(session_factory)
    return PersistenceContext(
        engine=engine,
        session_factory=session_factory,
        type_cache=type_cache,
        mappers=mappers,
        trade_repo=SqlAlchemyTradeRepository(type_cache, mappers),
        order_repo=SqlAlchemyOrderRepository(type_cache, mappers),
        universe_repo=SqlAlchemyStrategyUniverseRepository(),
        route_gate=SqlAlchemyRouteGate(),
        uow_factory=SqlAlchemyUnitOfWorkFactory(session_factory),
        outbox_publisher=SqlAlchemyOutboxPublisher(),
        outbox_reader=SqlAlchemyOutboxReader(),
        feed_run_repo=feed_run_repo,
        strategy_run_repo=strategy_run_repo,
        run_tracker=SqlAlchemyRunTracker(
            feed_run_repo=feed_run_repo,
            strategy_run_repo=strategy_run_repo,
        ),
        historical=TimescaleFeedStore(session_factory),
    )


def _build_messaging(redis, nc, historical: TimescaleFeedStore) -> MessagingContext:
    feed_cache = RedisFeedCache(redis)
    # Retained from the pre-refactor runner for parity — side effect only.
    RedisStateStore(redis)
    return MessagingContext(
        redis=redis,
        nc=nc,
        event_bus=RedisEventBus(redis),
        feed_cache=feed_cache,
        feed_store=CompositeFeedStore(latest=feed_cache, historical=historical),
        heartbeat_store=RedisHeartbeat(redis),
        durable_publisher=NatsJetStreamPublisher(nc),
    )


async def _safe_close_nats(nc) -> None:
    try:
        await nc.close()
    except Exception:
        logger.exception("Error closing NATS connection")
