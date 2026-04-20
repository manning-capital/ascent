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
    SqlAlchemyOutboxPublisher,
    SqlAlchemyOutboxReader,
    SqlAlchemyRouteGate,
    SqlAlchemyRunTracker,
    SqlAlchemyStrategyRunRepository,
    SqlAlchemyStrategyUniverseRepository,
    SqlAlchemyTradeRepository,
    SqlAlchemyUnitOfWorkFactory,
    SystemClock,
    TimescaleFeedStore,
    TypeCache,
)
from ascent.adapters.nats import NatsJetStreamPublisher, connect_nats, ensure_stream
from ascent.adapters.redis_asyncio import create_redis_client
from ascent.application import (
    DispatcherService,
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
    OutboxRelay,
    PeriodicReconciliationService,
    PersistenceService,
    ScheduledFeedService,
    StrategyEvaluator,
    StrategyFeedSpec,
    TriggeredFeedService,
)
from ascent.domain import OrderType
from ascent.engine.context import (
    _current_feeds,
    _current_logger,
    _current_snapshot,
    _current_universe,
)
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
        nats_url: str | None = None,
        include_writer: bool = False,
        log_level: str = "INFO",
    ) -> None:
        settings = Settings()
        self._database_url = database_url or settings.database_url
        self._redis_url = redis_url or settings.redis_url
        self._nats_url = nats_url or settings.nats_url
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

        nc = await connect_nats(self._nats_url, name="ascent-engine")
        logger.info("Connected to NATS at %s", self._nats_url)
        # Provision the dispatch + fill-response stream. Subject taxonomy:
        # - ascent.exchange.<exchange-id>            — dispatch
        # - ascent.exchange.<exchange-id>.responses  — fills (phase 7)
        # Both live on one stream; consumers use filter_subject to split.
        await ensure_stream(
            nc,
            stream_name="ASCENT_EXCHANGE",
            subjects=["ascent.exchange.>"],
        )

        event_bus = RedisEventBus(redis)
        feed_cache = RedisFeedCache(redis)
        RedisStateStore(redis)
        heartbeat_store = RedisHeartbeat(redis)

        type_cache = TypeCache(session_factory)
        mappers = OrmMappers(type_cache)

        trade_repo = SqlAlchemyTradeRepository(type_cache, mappers)
        order_repo = SqlAlchemyOrderRepository(type_cache, mappers)
        universe_repo = SqlAlchemyStrategyUniverseRepository()
        route_gate = SqlAlchemyRouteGate()
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        outbox_publisher = SqlAlchemyOutboxPublisher()
        outbox_reader = SqlAlchemyOutboxReader()
        durable_publisher = NatsJetStreamPublisher(nc)
        feed_run_repo = SqlAlchemyFeedRunRepository(session_factory)
        strategy_run_repo = SqlAlchemyStrategyRunRepository(session_factory)
        run_tracker = SqlAlchemyRunTracker(
            feed_run_repo=feed_run_repo, strategy_run_repo=strategy_run_repo
        )

        historical = TimescaleFeedStore(session_factory)
        feed_store = CompositeFeedStore(latest=feed_cache, historical=historical)

        clock = SystemClock()
        executor = FeedExecutor(feed_store=feed_store, event_bus=event_bus)

        deployment = await asyncio.to_thread(self._deploy_all, engine)
        feed_records = await asyncio.to_thread(self._load_feed_records, session_factory, deployment)
        await asyncio.to_thread(self._reconcile_strategy_universes, session_factory, deployment)

        fill_processor = FillProcessor(
            trade_repo=trade_repo,
            order_repo=order_repo,
            event_bus=event_bus,
            uow_factory=uow_factory,
        )
        reconciler = OrderReconciler(
            order_repo=order_repo,
            fill_processor=fill_processor,
            trade_repo=trade_repo,
            uow_factory=uow_factory,
        )
        persister = FeedPersister(
            latest_store=feed_cache,
            historical_store=historical,
            attribute_resolver=type_cache,
        )

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
                        session_factory,
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
                        universe_repo=universe_repo,
                        route_gate=route_gate,
                        outbox=outbox_publisher,
                        uow_factory=uow_factory,
                        run_tracker=run_tracker,
                        strategy_run_repo=strategy_run_repo,
                        clock=clock,
                        type_cache=type_cache,
                    )
                # Outbox relay: forwards durable events to the broker. In
                # phase-4 this shims to Redis pub/sub so existing ExchangeService
                # subscribers keep working. Phase 5 swaps the publisher for
                # NATS JetStream with no other changes.
                relay = OutboxRelay(
                    uow_factory=uow_factory,
                    reader=outbox_reader,
                    publisher=durable_publisher,
                    clock=clock,
                )
                tg.create_task(relay.run_forever(), name="outbox-relay")
                for exchange_cls in self._exchanges:
                    self._start_exchange(
                        tg=tg,
                        exchange_cls=exchange_cls,
                        deployment=deployment,
                        session_factory=session_factory,
                        event_bus=event_bus,
                        reconciler=reconciler,
                        clock=clock,
                        nc=nc,
                        durable_publisher=durable_publisher,
                    )
                if self._exchanges:
                    tg.create_task(
                        self._start_fill_handler(nc, fill_processor, clock),
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
            try:
                await nc.close()
            except Exception:
                logger.exception("Error closing NATS connection")
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

    def _reconcile_strategy_universes(
        self, session_factory: sessionmaker, deployment: _Deployment
    ) -> None:
        """Auto-disable drifted strategy universe items.

        For each strategy, walk active instrument/composite scope rows and
        flip ``is_active=False`` on any row that no longer has a tradeable
        exchange or a covering feed scope. Logs one line per drifted item so
        the operator can see what was disabled on boot.
        """
        from ascent.server.services.universe_service import reconcile_strategy_universe

        with Session(bind=session_factory.kw["bind"]) as db:
            for sid in deployment.strategy_ids.values():
                drift = reconcile_strategy_universe(db, sid)
                for item in drift:
                    logger.warning(
                        "Auto-disabled drifted %s item %s on strategy %s: %s",
                        item.scope_type,
                        item.item_id,
                        item.strategy_id,
                        item.reason,
                    )

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
        session_factory,
    ) -> None:
        fid = next(k for k, v in feed_records.items() if v["cls"] is feed_cls)
        record = feed_records[fid]["model"]
        is_composite_scoped = feed_records[fid]["is_composite_scoped"]
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

        factory = _fetcher_factory(
            feed_cls,
            record.parameters or {},
            feed_id=fid,
            is_composite_scoped=is_composite_scoped,
            session_factory=session_factory,
        )

        if feed_cls.schedule is not None:
            service = ScheduledFeedService(
                feed=feed_ctx,
                executor=executor,
                run_tracker=run_tracker,
                clock=clock,
                fetcher_factory=factory,
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
                fetcher_factory=factory,
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
        universe_repo,
        route_gate,
        outbox,
        uow_factory,
        run_tracker,
        strategy_run_repo,
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

        if scope == "composite":
            composite_members = await asyncio.to_thread(
                self._load_composite_members, session_factory
            )

        strategy_instance = strategy_cls(strategy_info["parameters"])
        router: TradeRouter | None = None
        if strategy_info["exchanges"]:
            router = TradeRouter(
                strategy_id=sid,
                portfolio_id=strategy_info["portfolio_id"],
                trade_repo=trade_repo,
                order_repo=order_repo,
                event_bus=event_bus,
                outbox=outbox,
                uow_factory=uow_factory,
                exchanges=[
                    ExchangeBinding(exchange_id=eid, channel=f"ascent.exchange.{eid}")
                    for eid in strategy_info["exchanges"]
                ],
                route_gate=route_gate,
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
            universe_repo=universe_repo,
            feed_store=feed_cache,
            event_bus=event_bus,
            run_tracker=run_tracker,
            strategy_run_repo=strategy_run_repo,
            clock=clock,
            evaluator=evaluator,
            uow_factory=uow_factory,
        )
        tg.create_task(evaluator_service.run_forever(), name=f"strategy-{strategy_cls.__name__}")

    def _load_composite_members(
        self, session_factory
    ) -> dict[uuid.UUID, list[uuid.UUID]]:
        """Load every composite's ordered instrument members.

        Composite-scoped strategies need this mapping to build the
        ``(composite_id, instrument_id)`` MultiIndex that backs ``ctx.df``.
        Returned list is ordered by ``CompositeMember.order``.
        """
        from ascent.database.models.composites import CompositeMember

        members: dict[uuid.UUID, list[uuid.UUID]] = {}
        with Session(bind=session_factory.kw["bind"]) as db:
            rows = (
                db.query(CompositeMember)
                .order_by(CompositeMember.composite_id, CompositeMember.order)
                .all()
            )
            for row in rows:
                members.setdefault(row.composite_id, []).append(row.instrument_id)
        return members

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
        nc,
        durable_publisher,
    ) -> None:
        from ascent.adapters.nats import NatsJetStreamConsumer
        from ascent.database.models.exchanges import Exchange as ExchangeModel

        eid = deployment.exchange_ids[exchange_cls.ref()]
        with Session(bind=session_factory.kw["bind"]) as db:
            record = db.get(ExchangeModel, eid)
        config = record.config if record else {}
        exchange_instance = exchange_cls(config)
        adapter = ExchangeAdapter(exchange_instance)
        dispatch_channel = f"ascent.exchange.{eid}"
        responses_channel = f"{dispatch_channel}.responses"

        # Dispatcher consumes dispatch intents from JetStream and forwards to
        # the exchange. Durable consumer name is per-exchange so restart
        # resumes the cursor.
        consumer = NatsJetStreamConsumer(
            nc,
            stream="ASCENT_EXCHANGE",
            subject_filter=dispatch_channel,
            durable_name=f"dispatcher-{eid}",
        )
        # The dispatcher and exchange-fill loop both publish responses to
        # JetStream via the same durable publisher (msg_id keyed on
        # exchange_order_id + status dedups redeliveries).
        dispatcher = DispatcherService(
            exchange_id=eid,
            exchange=adapter,
            consumer=consumer,
            responses_subject=responses_channel,
            responses_publisher=durable_publisher,
            clock=clock,
        )
        tg.create_task(dispatcher.run_forever(), name=f"dispatcher-{exchange_cls.__name__}")

        fill_service = ExchangeService(
            exchange_id=eid,
            exchange=adapter,
            responses_subject=responses_channel,
            responses_publisher=durable_publisher,
            reconciler=reconciler,
            clock=clock,
            open_orders=dispatcher.open_orders,
        )
        tg.create_task(fill_service.run_forever(), name=f"exchange-{exchange_cls.__name__}")

        # Layer-2 stuck-trade defense: re-run the reconciler every 5 minutes.
        # Catches any fill that slipped past the live stream/poll path.
        reconcile_service = PeriodicReconciliationService(
            reconciler=reconciler,
            exchange=adapter,
            exchange_id=eid,
            clock=clock,
            interval_seconds=300.0,
        )
        tg.create_task(
            reconcile_service.run_forever(),
            name=f"reconcile-{exchange_cls.__name__}",
        )

    async def _start_fill_handler(self, nc, fill_processor, clock) -> None:
        from ascent.adapters.nats import NatsJetStreamConsumer

        # One durable consumer across all exchanges. The filter_subject
        # ``ascent.exchange.*.responses`` matches every exchange's fill
        # channel. The ``*`` matches one token (the exchange UUID).
        consumer = NatsJetStreamConsumer(
            nc,
            stream="ASCENT_EXCHANGE",
            subject_filter="ascent.exchange.*.responses",
            durable_name="fill-handler",
        )
        service = FillHandlerService(
            consumer=consumer,
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


def _fetcher_factory(
    feed_cls: type,
    parameters: dict,
    *,
    feed_id: uuid.UUID,
    is_composite_scoped: bool,
    session_factory,
) -> Any:
    """Return a factory that builds a FeedFetcher for one execution tick.

    The factory is given the snapshot timestamp and parent-feed context; it
    returns a ``FeedFetcher`` whose ``fetch`` method runs user code on a
    threadpool and sets the Ascent contextvars before the call.
    """

    def factory(snapshot_timestamp, context):  # noqa: ANN001
        return _FeedFetcherBridge(
            feed_cls=feed_cls,
            parameters=parameters,
            feed_id=feed_id,
            is_composite_scoped=is_composite_scoped,
            session_factory=session_factory,
        )

    return factory


class _FeedFetcherBridge(FeedFetcher):
    def __init__(
        self,
        feed_cls: type,
        parameters: dict,
        *,
        feed_id: uuid.UUID,
        is_composite_scoped: bool,
        session_factory,
    ) -> None:
        self._feed_cls = feed_cls
        self._parameters = parameters
        self._feed_id = feed_id
        self._is_composite_scoped = is_composite_scoped
        self._session_factory = session_factory
        self._instance = feed_cls(parameters)

    async def fetch(self, snapshot_timestamp, context):  # noqa: ANN001
        def _call() -> Any:
            universe = self._load_universe()
            token_universe = _current_universe.set(universe)
            token_feeds = _current_feeds.set(context) if context else None
            token_snapshot = _current_snapshot.set(snapshot_timestamp)
            token_logger = _current_logger.set(logger)
            try:
                return self._instance.fetch()
            finally:
                _current_logger.reset(token_logger)
                _current_snapshot.reset(token_snapshot)
                if token_feeds is not None:
                    _current_feeds.reset(token_feeds)
                _current_universe.reset(token_universe)

        return await asyncio.to_thread(_call)

    def _load_universe(self) -> list[uuid.UUID]:
        from sqlalchemy import select

        from ascent.database.models.feeds import FeedCompositeScope, FeedInstrumentScope

        with self._session_factory() as db:
            if self._is_composite_scoped:
                rows = db.execute(
                    select(FeedCompositeScope.composite_id)
                    .where(FeedCompositeScope.feed_id == self._feed_id)
                    .where(FeedCompositeScope.is_active.is_(True))
                    .order_by(FeedCompositeScope.order)
                ).all()
            else:
                rows = db.execute(
                    select(FeedInstrumentScope.instrument_id)
                    .where(FeedInstrumentScope.feed_id == self._feed_id)
                    .where(FeedInstrumentScope.is_active.is_(True))
                    .order_by(FeedInstrumentScope.order)
                ).all()
        return [r[0] for r in rows]

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
