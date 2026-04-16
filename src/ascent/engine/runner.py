"""Async composition root for the Ascent engine.

Wires adapters → ports → use cases → runtime services under a single
``asyncio.TaskGroup``. Kept deliberately thin: no business logic, no state
transitions — it only constructs the object graph and owns task lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ascent.adapters import (
    CompositeFeedStore,
    ExchangeAdapter,
    OrmMappers,
    RedisEventBus,
    RedisFeedCache,
    RedisHeartbeat,
    RedisStateStore,
    SqlAlchemyFeedRunRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyPartitionRepository,
    SqlAlchemyRunTracker,
    SqlAlchemyStrategyRunRepository,
    SqlAlchemyTradeRepository,
    SystemClock,
    TimescaleFeedStore,
    TypeCache,
)
from ascent.adapters.redis_asyncio import create_redis_client
from ascent.application import (
    ExchangeService,
    FeedBinding,
    FeedContext,
    FeedExecutor,
    FeedFetcher,
    FeedPersister,
    FillHandlerService,
    FillProcessor,
    HeartbeatService,
    OrderReconciler,
    PersistenceService,
    ScheduledFeedService,
    StrategyEvaluator,
    StrategyFeedSpec,
    TriggeredFeedService,
)
from ascent.domain import OrderType
from ascent.engine.context import PartitionInfo, _current_feeds, _current_logger, _current_partition
from ascent.engine.deploy import deploy_exchange, deploy_feed, deploy_strategy
from ascent.feeds.schedule import Schedule
from ascent.server.config import Settings

if TYPE_CHECKING:
    from ascent.exchanges.base import BaseExchange
    from ascent.feeds.base import Feed
    from ascent.strategies.base import Strategy

logger = logging.getLogger(__name__)


def _topological_sort_feeds(feed_classes: list[type[Feed]]) -> list[type[Feed]]:
    ref_to_cls = {cls.ref(): cls for cls in feed_classes}
    in_degree = {cls.ref(): 0 for cls in feed_classes}
    dependents: dict[str, list[str]] = {cls.ref(): [] for cls in feed_classes}
    for cls in feed_classes:
        if cls.depends_on:
            for parent_cls in cls.depends_on:
                parent_ref = parent_cls.ref()
                if parent_ref in ref_to_cls:
                    in_degree[cls.ref()] += 1
                    dependents[parent_ref].append(cls.ref())
    queue = [ref for ref, deg in in_degree.items() if deg == 0]
    result: list[type[Feed]] = []
    while queue:
        ref = queue.pop(0)
        result.append(ref_to_cls[ref])
        for child_ref in dependents[ref]:
            in_degree[child_ref] -= 1
            if in_degree[child_ref] == 0:
                queue.append(child_ref)
    if len(result) != len(feed_classes):
        raise ValueError("Circular dependency detected among feeds")
    return result


@dataclass
class _Deployment:
    feed_ids: dict[str, uuid.UUID]
    strategy_ids: dict[str, uuid.UUID]
    exchange_ids: dict[str, uuid.UUID]


class Runner:
    """Auto-deploys registered objects and runs them under an asyncio TaskGroup."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        redis_url: str | None = None,
        include_writer: bool = False,
        log_level: str = "INFO",
    ) -> None:
        settings = Settings()
        self._database_url = database_url or settings.database_url
        self._redis_url = redis_url or settings.redis_url
        self._include_writer = include_writer
        self._log_level = log_level
        self._feeds: list[type[Feed]] = []
        self._strategies: list[type[Strategy]] = []
        self._exchanges: list[type[BaseExchange]] = []

    def add(self, obj: type) -> Runner:
        from ascent.exchanges.base import BaseExchange
        from ascent.feeds.base import Feed
        from ascent.strategies.base import Strategy

        if isinstance(obj, type) and issubclass(obj, Feed) and obj is not Feed:
            self._feeds.append(obj)
        elif isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            self._strategies.append(obj)
        elif isinstance(obj, type) and issubclass(obj, BaseExchange) and obj is not BaseExchange:
            self._exchanges.append(obj)
        else:
            raise TypeError(f"Expected a Feed, Strategy, or Exchange subclass, got {obj!r}")
        return self

    def run(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self._log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        engine = create_engine(self._database_url)
        session_factory = sessionmaker(bind=engine)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to database at %s", self._database_url)

        redis = create_redis_client(self._redis_url)
        await redis.ping()
        logger.info("Connected to Redis at %s", self._redis_url)

        event_bus = RedisEventBus(redis)
        feed_cache = RedisFeedCache(redis)
        RedisStateStore(redis)
        heartbeat_store = RedisHeartbeat(redis)

        type_cache = TypeCache(session_factory)
        mappers = OrmMappers(type_cache)

        trade_repo = SqlAlchemyTradeRepository(session_factory, type_cache, mappers)
        order_repo = SqlAlchemyOrderRepository(session_factory, type_cache, mappers)
        feed_run_repo = SqlAlchemyFeedRunRepository(session_factory)
        strategy_run_repo = SqlAlchemyStrategyRunRepository(session_factory)
        partition_repo = SqlAlchemyPartitionRepository(session_factory)
        run_tracker = SqlAlchemyRunTracker(
            feed_run_repo=feed_run_repo, strategy_run_repo=strategy_run_repo
        )

        historical = TimescaleFeedStore(session_factory)
        feed_store = CompositeFeedStore(latest=feed_cache, historical=historical)

        clock = SystemClock()
        executor = FeedExecutor(
            feed_store=feed_store, event_bus=event_bus, partition_repo=partition_repo
        )

        deployment = await asyncio.to_thread(self._deploy_all, engine)
        feed_records = await asyncio.to_thread(self._load_feed_records, session_factory, deployment)

        fill_processor = FillProcessor(
            trade_repo=trade_repo, order_repo=order_repo, event_bus=event_bus
        )
        reconciler = OrderReconciler(
            order_repo=order_repo,
            fill_processor=fill_processor,
            trade_repo=trade_repo,
        )
        persister = FeedPersister(latest_store=feed_cache, historical_store=historical)

        shutdown = asyncio.Event()
        self._install_signal_handlers(shutdown)

        heartbeat_service = HeartbeatService(
            heartbeat_store=heartbeat_store,
            targets=self._heartbeat_targets(deployment),
        )

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(heartbeat_service.run_forever(), name="heartbeat")
                for feed_cls in self._feeds:
                    self._start_feed(
                        tg,
                        feed_cls,
                        feed_records,
                        executor,
                        run_tracker,
                        event_bus,
                        feed_cache,
                        clock,
                    )
                for strategy_cls in self._strategies:
                    await self._start_strategy(
                        tg=tg,
                        strategy_cls=strategy_cls,
                        deployment=deployment,
                        session_factory=session_factory,
                        event_bus=event_bus,
                        feed_cache=feed_cache,
                        trade_repo=trade_repo,
                        order_repo=order_repo,
                        run_tracker=run_tracker,
                        clock=clock,
                        type_cache=type_cache,
                    )
                for exchange_cls in self._exchanges:
                    self._start_exchange(
                        tg=tg,
                        exchange_cls=exchange_cls,
                        deployment=deployment,
                        session_factory=session_factory,
                        event_bus=event_bus,
                        reconciler=reconciler,
                        clock=clock,
                    )
                if self._exchanges:
                    tg.create_task(
                        self._start_fill_handler(session_factory, event_bus, fill_processor, clock),
                        name="fill-handler",
                    )
                if self._include_writer:
                    self._start_persister(tg, feed_records, event_bus, persister)

                self._log_banner(deployment)

                await shutdown.wait()
                logger.info("Shutdown requested — cancelling tasks")
                raise asyncio.CancelledError
        except* asyncio.CancelledError:
            # Expected on shutdown; every child task raises CancelledError in turn.
            pass
        finally:
            await redis.aclose()
            logger.info("Runner shut down cleanly")

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    def _deploy_all(self, engine) -> _Deployment:
        sorted_feeds = _topological_sort_feeds(self._feeds)
        feed_ids: dict[str, uuid.UUID] = {}
        strategy_ids: dict[str, uuid.UUID] = {}
        exchange_ids: dict[str, uuid.UUID] = {}
        with Session(engine) as db:
            for feed_cls in sorted_feeds:
                feed_ids[feed_cls.ref()] = deploy_feed(feed_cls, db)
            for strategy_cls in self._strategies:
                strategy_ids[strategy_cls.ref()] = deploy_strategy(strategy_cls, db)
            for exchange_cls in self._exchanges:
                exchange_ids[exchange_cls.ref()] = deploy_exchange(exchange_cls, db)
            db.commit()
        return _Deployment(feed_ids, strategy_ids, exchange_ids)

    def _load_feed_records(
        self, session_factory: sessionmaker, deployment: _Deployment
    ) -> dict[uuid.UUID, dict]:
        from ascent.database.models.feeds import Feed as FeedModel
        from ascent.database.models.feeds import FeedDependency

        records: dict[uuid.UUID, dict] = {}
        with Session(bind=session_factory.kw["bind"]) as db:
            for feed_cls in self._feeds:
                fid = deployment.feed_ids[feed_cls.ref()]
                record = db.get(FeedModel, fid)
                if record is None:
                    continue
                deps = db.query(FeedDependency).filter(FeedDependency.feed_id == fid).all()
                dep_ids = [d.depends_on_feed_id for d in deps]
                parent_records = {dep_id: db.get(FeedModel, dep_id) for dep_id in dep_ids}
                records[fid] = {
                    "cls": feed_cls,
                    "model": record,
                    "parent_records": parent_records,
                    "is_composite_scoped": record.composite_type_id is not None,
                }
        return records

    def _heartbeat_targets(self, deployment: _Deployment) -> list[tuple[str, uuid.UUID]]:
        targets: list[tuple[str, uuid.UUID]] = []
        for fid in deployment.feed_ids.values():
            targets.append(("feed", fid))
        for sid in deployment.strategy_ids.values():
            targets.append(("strategy", sid))
        for eid in deployment.exchange_ids.values():
            targets.append(("exchange", eid))
        return targets

    # ------------------------------------------------------------------
    # Feeds
    # ------------------------------------------------------------------

    def _start_feed(
        self,
        tg: asyncio.TaskGroup,
        feed_cls: type[Feed],
        feed_records: dict[uuid.UUID, dict],
        executor: FeedExecutor,
        run_tracker,
        event_bus,
        feed_cache,
        clock,
    ) -> None:
        fid = next(k for k, v in feed_records.items() if v["cls"] is feed_cls)
        record = feed_records[fid]["model"]
        feed_ctx = FeedContext(
            feed_id=fid,
            feed_ref=record.feed_ref,
            channel=record.channel,
            output_table=record.output_table,
            schedule=Schedule(**record.schedule) if record.schedule else None,
        )

        if feed_cls.is_streaming():
            logger.warning("Streaming feed %s not yet supported, skipping", feed_cls.ref())
            return

        if feed_cls.schedule is not None:
            service = ScheduledFeedService(
                feed=feed_ctx,
                executor=executor,
                run_tracker=run_tracker,
                clock=clock,
                fetcher_factory=_fetcher_factory(feed_cls, record.parameters or {}),
            )
            tg.create_task(service.run_forever(), name=f"feed-{feed_cls.__name__}")
            return

        if feed_cls.depends_on:
            parents = feed_records[fid]["parent_records"]
            parent_channels = [p.channel for p in parents.values() if p]
            parent_refs = {p.id: p.feed_ref for p in parents.values() if p}
            parent_schedules = [
                Schedule(**p.schedule) for p in parents.values() if p and p.schedule
            ]
            effective = min(parent_schedules, key=lambda s: s.interval, default=None)
            service = TriggeredFeedService(
                feed=feed_ctx,
                parent_channels=parent_channels,
                parent_refs=parent_refs,
                effective_schedule=effective,
                executor=executor,
                run_tracker=run_tracker,
                event_bus=event_bus,
                feed_store=feed_cache,
                fetcher_factory=_fetcher_factory(feed_cls, record.parameters or {}),
            )
            tg.create_task(service.run_forever(), name=f"feed-{feed_cls.__name__}")
            return

        logger.info("Feed %s is external (no schedule or depends_on), skipping", feed_cls.ref())

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    async def _start_strategy(
        self,
        *,
        tg: asyncio.TaskGroup,
        strategy_cls,
        deployment: _Deployment,
        session_factory,
        event_bus,
        feed_cache,
        trade_repo,
        order_repo,
        run_tracker,
        clock,
        type_cache: TypeCache,
    ) -> None:
        from ascent.application.route_trade import ExchangeBinding, TradeRouter

        sid = deployment.strategy_ids[strategy_cls.ref()]
        strategy_info = await asyncio.to_thread(self._load_strategy_info, session_factory, sid)

        feeds: list[FeedBinding] = []
        scope = "instrument"
        composite_members: dict[uuid.UUID, list[uuid.UUID]] = {}
        for feed_spec in strategy_info["feed_specs"]:
            feeds.append(
                FeedBinding(
                    spec=StrategyFeedSpec(
                        feed_id=feed_spec["feed_id"],
                        is_required=feed_spec["is_required"],
                    ),
                    feed_ref=feed_spec["feed_ref"],
                    channel=feed_spec["channel"],
                    is_composite_scoped=feed_spec["is_composite_scoped"],
                )
            )
            if feed_spec["is_composite_scoped"]:
                scope = "composite"

        strategy_instance = strategy_cls(strategy_info["parameters"])
        router: TradeRouter | None = None
        if strategy_info["exchanges"]:
            router = TradeRouter(
                strategy_id=sid,
                portfolio_id=strategy_info["portfolio_id"],
                trade_repo=trade_repo,
                order_repo=order_repo,
                event_bus=event_bus,
                exchanges=[
                    ExchangeBinding(exchange_id=eid, channel=f"ascent.exchange.{eid}")
                    for eid in strategy_info["exchanges"]
                ],
            )
            strategy_instance._trade_router = _SyncRouterProxy(router, asyncio.get_running_loop())

        async def evaluator(ctx, run_id: uuid.UUID) -> None:
            if router is not None:
                router.bind_strategy_run(run_id)
            token = _current_logger.set(logger)
            try:
                await asyncio.to_thread(strategy_instance.evaluate, ctx)
            finally:
                _current_logger.reset(token)

        evaluator_service = StrategyEvaluator(
            strategy_id=sid,
            feeds=feeds,
            scope=scope,
            composite_members=composite_members,
            trade_repo=trade_repo,
            feed_store=feed_cache,
            event_bus=event_bus,
            run_tracker=run_tracker,
            clock=clock,
            evaluator=evaluator,
            attribute_map=type_cache.attribute_map,
        )
        tg.create_task(evaluator_service.run_forever(), name=f"strategy-{strategy_cls.__name__}")

    def _load_strategy_info(self, session_factory, strategy_id: uuid.UUID) -> dict:
        from ascent.database.models.exchanges import Exchange as ExchangeModel
        from ascent.database.models.feeds import Feed as FeedModel
        from ascent.database.models.feeds import StrategyFeed
        from ascent.database.models.strategy import Strategy as StrategyModel
        from ascent.database.models.strategy import StrategyExchange

        with Session(bind=session_factory.kw["bind"]) as db:
            record = db.get(StrategyModel, strategy_id)
            if record is None:
                raise ValueError(f"Strategy {strategy_id} not found")
            feed_specs = []
            sf_rows = (
                db.query(StrategyFeed)
                .filter(StrategyFeed.strategy_id == strategy_id)
                .order_by(StrategyFeed.order)
                .all()
            )
            for sf in sf_rows:
                feed = db.get(FeedModel, sf.feed_id)
                if feed is None:
                    continue
                feed_specs.append(
                    {
                        "feed_id": feed.id,
                        "is_required": sf.is_required,
                        "feed_ref": feed.feed_ref,
                        "channel": feed.channel,
                        "is_composite_scoped": feed.composite_type_id is not None,
                    }
                )
            exchanges: list[uuid.UUID] = []
            se_rows = (
                db.query(StrategyExchange)
                .filter(StrategyExchange.strategy_id == strategy_id)
                .order_by(StrategyExchange.order)
                .all()
            )
            for se in se_rows:
                ex = db.get(ExchangeModel, se.exchange_id)
                if ex and ex.is_active:
                    exchanges.append(ex.id)
            return {
                "parameters": record.parameters or {},
                "portfolio_id": record.portfolio_id,
                "feed_specs": feed_specs,
                "exchanges": exchanges,
            }

    # ------------------------------------------------------------------
    # Exchanges + fill handler + persistence
    # ------------------------------------------------------------------

    def _start_exchange(
        self,
        *,
        tg: asyncio.TaskGroup,
        exchange_cls,
        deployment: _Deployment,
        session_factory,
        event_bus,
        reconciler,
        clock,
    ) -> None:
        from ascent.database.models.exchanges import Exchange as ExchangeModel

        eid = deployment.exchange_ids[exchange_cls.ref()]
        with Session(bind=session_factory.kw["bind"]) as db:
            record = db.get(ExchangeModel, eid)
        config = record.config if record else {}
        exchange_instance = exchange_cls(config)
        adapter = ExchangeAdapter(exchange_instance)
        service = ExchangeService(
            exchange_id=eid,
            exchange=adapter,
            channel=f"ascent.exchange.{eid}",
            event_bus=event_bus,
            reconciler=reconciler,
            clock=clock,
        )
        tg.create_task(service.run_forever(), name=f"exchange-{exchange_cls.__name__}")

    async def _start_fill_handler(self, session_factory, event_bus, fill_processor, clock) -> None:
        from ascent.database.models.exchanges import Exchange as ExchangeModel

        def _load_channels() -> list[str]:
            with Session(bind=session_factory.kw["bind"]) as db:
                rows = db.query(ExchangeModel).filter(ExchangeModel.is_active.is_(True)).all()
                return [f"ascent.exchange.{ex.id}.responses" for ex in rows]

        channels = await asyncio.to_thread(_load_channels)
        if not channels:
            logger.warning("FillHandler: no active exchanges; skipping")
            return
        service = FillHandlerService(
            response_channels=channels,
            event_bus=event_bus,
            processor=fill_processor,
            clock=clock,
        )
        await service.run_forever()

    def _start_persister(
        self,
        tg: asyncio.TaskGroup,
        feed_records: dict[uuid.UUID, dict],
        event_bus,
        persister,
    ) -> None:
        channels = [fr["model"].channel for fr in feed_records.values()]
        feed_to_output = {fid: fr["model"].output_table for fid, fr in feed_records.items()}
        service = PersistenceService(
            feed_channels=channels,
            feed_id_to_output=feed_to_output,
            event_bus=event_bus,
            persister=persister,
        )
        tg.create_task(service.run_forever(), name="db-writer")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _install_signal_handlers(self, shutdown: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()

        def _on_signal(signum: int) -> None:
            logger.info("Received signal %s, shutting down", signum)
            shutdown.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _on_signal, sig)
            except NotImplementedError:
                # Windows: fall back to default; we'll still honour Ctrl-C.
                pass

    def _log_banner(self, deployment: _Deployment) -> None:
        lines = ["", "=" * 60, "  Ascent Runner (async)", "=" * 60]
        if deployment.feed_ids:
            lines.append("  Feeds:")
            for ref, fid in deployment.feed_ids.items():
                lines.append(f"    {ref}  ({fid})")
        if deployment.strategy_ids:
            lines.append("  Strategies:")
            for ref, sid in deployment.strategy_ids.items():
                lines.append(f"    {ref}  ({sid})")
        if deployment.exchange_ids:
            lines.append("  Exchanges:")
            for ref, eid in deployment.exchange_ids.items():
                lines.append(f"    {ref}  ({eid})")
        lines.append("=" * 60)
        logger.info("\n".join(lines))


# ---------------------------------------------------------------------------
# Feed fetcher bridge — wraps sync user Feed.fetch() as a FeedFetcher Protocol
# ---------------------------------------------------------------------------


def _fetcher_factory(feed_cls: type, parameters: dict) -> Any:
    """Return a factory that builds a FeedFetcher for one execution tick.

    The factory is given the partition window and parent-feed context; it
    returns a ``FeedFetcher`` whose ``fetch`` method runs user code on a
    threadpool and sets the Ascent contextvars before the call.
    """

    def factory(partition, context):  # noqa: ANN001
        return _FeedFetcherBridge(feed_cls=feed_cls, parameters=parameters)

    return factory


class _FeedFetcherBridge(FeedFetcher):
    def __init__(self, feed_cls: type, parameters: dict) -> None:
        self._feed_cls = feed_cls
        self._parameters = parameters
        self._instance = feed_cls(parameters)

    async def fetch(self, partition, context):  # noqa: ANN001
        def _call() -> Any:
            token_feeds = _current_feeds.set(context) if context else None
            token_partition = (
                _current_partition.set(
                    PartitionInfo(
                        key=partition.key,
                        window_start=partition.window_start,
                        window_end=partition.window_end,
                    )
                )
                if partition is not None
                else None
            )
            token_logger = _current_logger.set(logger)
            try:
                return self._instance.fetch()
            finally:
                _current_logger.reset(token_logger)
                if token_partition is not None:
                    _current_partition.reset(token_partition)
                if token_feeds is not None:
                    _current_feeds.reset(token_feeds)

        return await asyncio.to_thread(_call)

    async def on_error(self, error: BaseException) -> None:
        await asyncio.to_thread(self._instance.on_error, error)


# ---------------------------------------------------------------------------
# Strategy side: router proxy adapts the async TradeRouter to sync calls
# from within evaluate(), which user code expects.
# ---------------------------------------------------------------------------


class _SyncRouterProxy:
    """Calls the async TradeRouter from a sync ``evaluate()`` running on a worker thread.

    Captures the main event loop at construction time so
    ``asyncio.run_coroutine_threadsafe`` has something to target. Returns the
    ``TradeDraft`` dataclass unchanged — user code accesses ``result.state`` /
    ``result.trade_id`` / ``result.leg_summaries`` directly.
    """

    def __init__(self, router, loop: asyncio.AbstractEventLoop) -> None:
        self._router = router
        self._loop = loop

    def submit(self, **kwargs):
        import datetime as _dt

        kwargs.setdefault("order_type", OrderType.MARKET)
        if isinstance(kwargs["order_type"], str):
            kwargs["order_type"] = OrderType(kwargs["order_type"])

        now = _dt.datetime.now(tz=_dt.UTC)
        return _run_in_loop(self._router.submit(now=now, **kwargs), self._loop)

    def close(self, **kwargs):
        import datetime as _dt

        if isinstance(kwargs.get("order_type"), str):
            kwargs["order_type"] = OrderType(kwargs["order_type"])

        now = _dt.datetime.now(tz=_dt.UTC)
        return _run_in_loop(self._router.close(now=now, **kwargs), self._loop)

    def get_open_trades(self):
        return _run_in_loop(self._router.get_open_trades(), self._loop)


def _run_in_loop(coro, loop: asyncio.AbstractEventLoop):
    # Schedules onto the main loop and blocks the worker thread until done.
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def serve(
    *objects: type,
    database_url: str | None = None,
    redis_url: str | None = None,
    include_writer: bool = False,
    log_level: str = "INFO",
) -> None:
    """Run multiple feeds, strategies, and/or exchanges in a single process."""
    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        include_writer=include_writer,
        log_level=log_level,
    )
    for obj in objects:
        runner.add(obj)
    runner.run()
