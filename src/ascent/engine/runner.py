"""Async composition root for the Ascent engine.

The Runner assembles infrastructure via :func:`build_infra`, deploys the
registered feed/strategy/exchange classes to the database, preloads the
startup read model, and hands the result to per-lifecycle launchers that
schedule their services under a single :class:`asyncio.TaskGroup`.

Task-group ordering (preserved across refactor, matters for correctness):

    heartbeat  →  feeds  →  strategies  →  outbox relay  →
    exchanges  →  fill handler (if any exchanges)  →  persister (if include_writer)

``OutboxRelay`` starts before any exchange so early dispatch publishes land
on a live relay; the heartbeat starts first so liveness data is available
from boot.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from typing import TYPE_CHECKING

from ascent.adapters import SystemClock
from ascent.application import (
    FeedExecutor,
    FeedPersister,
    FillProcessor,
    OrderReconciler,
)
from ascent.engine.bridges import _SyncRouterProxy  # noqa: F401 — re-export
from ascent.engine.build import RunnerConfig, build_infra
from ascent.engine.contexts import EngineContext, RuntimeContext
from ascent.engine.deployer import Deployer, Deployment
from ascent.engine.launchers import (
    ExchangeLauncher,
    FeedLauncher,
    GlobalServicesLauncher,
    StrategyLauncher,
)
from ascent.engine.queries import StartupQueries
from ascent.engine.sorting import _topological_sort_feeds  # noqa: F401 — re-export
from ascent.server.config import Settings

if TYPE_CHECKING:
    from ascent.exchanges.base import BaseExchange
    from ascent.feeds.base import Feed
    from ascent.strategies.base import Strategy

logger = logging.getLogger(__name__)


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
        self._cfg = RunnerConfig(
            database_url=database_url or settings.database_url,
            redis_url=redis_url or settings.redis_url,
            nats_url=nats_url or settings.nats_url,
        )
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
        persistence, messaging, stack = await build_infra(self._cfg)
        try:
            deployment = await asyncio.to_thread(
                Deployer(self._feeds, self._strategies, self._exchanges).deploy,
                persistence.engine,
            )
            runtime = await asyncio.to_thread(
                self._build_runtime, persistence, messaging, deployment
            )
            ctx = EngineContext(
                persistence=persistence,
                messaging=messaging,
                runtime=runtime,
                shutdown=asyncio.Event(),
                loop=asyncio.get_running_loop(),
            )

            self._install_signal_handlers(ctx.shutdown)

            feed_launcher = FeedLauncher(
                persistence=persistence, messaging=messaging, runtime=runtime
            )
            strategy_launcher = StrategyLauncher(
                persistence=persistence,
                messaging=messaging,
                runtime=runtime,
                loop=ctx.loop,
            )
            exchange_launcher = ExchangeLauncher(
                persistence=persistence, messaging=messaging, runtime=runtime
            )
            globals_launcher = GlobalServicesLauncher(
                persistence=persistence, messaging=messaging, runtime=runtime
            )

            try:
                async with asyncio.TaskGroup() as tg:
                    globals_launcher.launch_heartbeat(tg, self._heartbeat_targets(deployment))
                    for feed_cls in self._feeds:
                        feed_launcher.launch(tg, feed_cls)
                    for strategy_cls in self._strategies:
                        strategy_launcher.launch(tg, strategy_cls)
                    globals_launcher.launch_outbox_relay(tg)
                    for exchange_cls in self._exchanges:
                        exchange_launcher.launch(tg, exchange_cls)
                    if self._exchanges:
                        globals_launcher.launch_fill_handler(tg)
                    if self._include_writer:
                        globals_launcher.launch_persister(tg, runtime.feed_records)

                    self._log_banner(deployment)

                    await ctx.shutdown.wait()
                    logger.info("Shutdown requested — cancelling tasks")
                    raise asyncio.CancelledError
            except* asyncio.CancelledError:
                # Expected on shutdown; every child task raises CancelledError in turn.
                pass
        finally:
            await stack.aclose()
            logger.info("Runner shut down cleanly")

    def _build_runtime(
        self,
        persistence,
        messaging,
        deployment: Deployment,
    ) -> RuntimeContext:
        clock = SystemClock()
        executor = FeedExecutor(feed_store=messaging.feed_cache, event_bus=messaging.event_bus)
        fill_processor = FillProcessor(
            trade_repo=persistence.trade_repo,
            order_repo=persistence.order_repo,
            event_bus=messaging.event_bus,
            uow_factory=persistence.uow_factory,
            holdings_repo=persistence.holdings_repo,
            transactions_repo=persistence.transaction_repo,
            instrument_repo=persistence.instrument_repo,
        )
        reconciler = OrderReconciler(
            order_repo=persistence.order_repo,
            fill_processor=fill_processor,
            trade_repo=persistence.trade_repo,
            uow_factory=persistence.uow_factory,
            event_bus=messaging.event_bus,
        )
        persister = FeedPersister(
            latest_store=messaging.feed_cache,
            historical_store=persistence.historical,
            attribute_resolver=persistence.type_cache,
        )

        queries = StartupQueries(persistence.session_factory)
        feed_records = queries.load_feed_records(self._feeds, deployment)
        queries.reconcile_universes(deployment)
        composite_members = queries.load_composite_members()
        strategy_info_by_id = {
            sid: queries.load_strategy_info(sid) for sid in deployment.strategy_ids.values()
        }

        return RuntimeContext(
            clock=clock,
            executor=executor,
            fill_processor=fill_processor,
            reconciler=reconciler,
            persister=persister,
            deployment=deployment,
            feed_records=feed_records,
            strategy_info_by_id=strategy_info_by_id,
            composite_members=composite_members,
        )

    def _heartbeat_targets(self, deployment: Deployment) -> list[tuple[str, uuid.UUID]]:
        targets: list[tuple[str, uuid.UUID]] = []
        targets.extend(("feed", fid) for fid in deployment.feed_ids.values())
        targets.extend(("strategy", sid) for sid in deployment.strategy_ids.values())
        targets.extend(("exchange", eid) for eid in deployment.exchange_ids.values())
        return targets

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

    def _log_banner(self, deployment: Deployment) -> None:
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
