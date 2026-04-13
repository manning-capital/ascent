"""Runner — auto-deploy, heartbeat, and engine loop orchestration.

The ``Runner`` class is the central runtime that bridges the user-facing
``Feed.run()`` / ``Strategy.run()`` / ``serve()`` API with the existing
engine functions (``run_scheduled_feed``, ``run_triggered_feed``,
``run_strategy``, ``run_streaming_feed``).

Lifecycle:
    1. Resolve config (args → env vars → Settings defaults)
    2. Create DB engine + Redis cache, verify connectivity
    3. Auto-deploy all registered objects (topological sort for feeds)
    4. Start heartbeat daemon thread
    5. Start one engine thread per object
    6. Block until SIGINT/SIGTERM, then join all threads
"""

from __future__ import annotations

import logging
import signal
import threading
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ascent.engine.cache import EngineCache
from ascent.engine.deploy import deploy_feed, deploy_strategy
from ascent.server.config import Settings

if TYPE_CHECKING:
    from ascent.feeds.base import Feed
    from ascent.strategies.base import Strategy

logger = logging.getLogger(__name__)


def _topological_sort_feeds(feed_classes: list[type[Feed]]) -> list[type[Feed]]:
    """Sort feed classes so parents come before dependents.

    Uses Kahn's algorithm.  Feed classes not in the input list are ignored
    (they must already be deployed in the DB).
    """
    # Build adjacency: child → set of parents (within our list)
    ref_to_cls = {cls.ref(): cls for cls in feed_classes}
    in_degree: dict[str, int] = {cls.ref(): 0 for cls in feed_classes}
    dependents: dict[str, list[str]] = {cls.ref(): [] for cls in feed_classes}

    for cls in feed_classes:
        if cls.depends_on:
            for parent_cls in cls.depends_on:
                parent_ref = parent_cls.ref()
                if parent_ref in ref_to_cls:
                    in_degree[cls.ref()] += 1
                    dependents[parent_ref].append(cls.ref())

    # Kahn's: start with zero in-degree
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
        raise ValueError("Circular dependency detected among feeds. Check depends_on declarations.")

    return result


class Runner:
    """Orchestrates auto-deploy, heartbeat, and engine loops.

    Usage::

        runner = Runner()
        runner.add(MarketData)
        runner.add(MomentumStrategy)
        runner.run()  # blocks until SIGINT/SIGTERM

    Or via the convenience function::

        serve(MarketData, MomentumStrategy)
    """

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

    def add(self, obj: type) -> Runner:
        """Register a Feed or Strategy class to be run.  Returns self for chaining."""
        from ascent.feeds.base import Feed
        from ascent.strategies.base import Strategy

        if isinstance(obj, type) and issubclass(obj, Feed) and obj is not Feed:
            self._feeds.append(obj)
        elif isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            self._strategies.append(obj)
        else:
            raise TypeError(f"Expected a Feed or Strategy subclass, got {obj!r}")
        return self

    def run(self) -> None:
        """Auto-deploy all registered objects and start engine loops.

        Blocks until SIGINT/SIGTERM.
        """
        logging.basicConfig(level=getattr(logging, self._log_level.upper(), logging.INFO))

        # Setup infrastructure
        engine = create_engine(self._database_url)
        cache = EngineCache(self._redis_url)

        # Verify connectivity
        cache.ping()
        logger.info("Connected to Redis at %s", self._redis_url)
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to database at %s", self._database_url)

        # Deploy phase — topological sort feeds, then deploy all
        sorted_feeds = _topological_sort_feeds(self._feeds)
        feed_ids: dict[str, uuid.UUID] = {}
        strategy_ids: dict[str, uuid.UUID] = {}

        with Session(engine) as db:
            for feed_cls in sorted_feeds:
                feed_id = deploy_feed(feed_cls, db)
                feed_ids[feed_cls.ref()] = feed_id
            for strategy_cls in self._strategies:
                strategy_id = deploy_strategy(strategy_cls, db)
                strategy_ids[strategy_cls.ref()] = strategy_id
            db.commit()

        # Shared shutdown event
        shutdown_event = threading.Event()

        def _signal_handler(signum, _frame):
            logger.info("Received signal %s, shutting down runner", signum)
            shutdown_event.set()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        # Start heartbeat daemon
        all_heartbeat_targets: list[tuple[str, uuid.UUID]] = []
        for _ref, fid in feed_ids.items():
            all_heartbeat_targets.append(("feed", fid))
        for _ref, sid in strategy_ids.items():
            all_heartbeat_targets.append(("strategy", sid))

        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(cache, all_heartbeat_targets, shutdown_event),
            daemon=True,
            name="runner-heartbeat",
        )
        heartbeat_thread.start()

        # Start engine threads
        threads: list[threading.Thread] = []

        for feed_cls in sorted_feeds:
            fid = feed_ids[feed_cls.ref()]
            if feed_cls.is_streaming():
                # TODO: run_streaming_feed will be added in Step 4
                logger.warning(
                    "Streaming feed %s not yet supported in runner, skipping", feed_cls.ref()
                )
            elif feed_cls.schedule is not None:
                from ascent.engine.producer import run_scheduled_feed

                t = threading.Thread(
                    target=run_scheduled_feed,
                    args=(fid,),
                    kwargs={
                        "database_url": self._database_url,
                        "redis_url": self._redis_url,
                        "shutdown_event": shutdown_event,
                    },
                    name=f"feed-{feed_cls.__name__}",
                )
                threads.append(t)
            elif feed_cls.depends_on:
                from ascent.engine.producer import run_triggered_feed

                t = threading.Thread(
                    target=run_triggered_feed,
                    args=(fid,),
                    kwargs={
                        "database_url": self._database_url,
                        "redis_url": self._redis_url,
                        "shutdown_event": shutdown_event,
                    },
                    name=f"feed-{feed_cls.__name__}",
                )
                threads.append(t)
            else:
                logger.info(
                    "Feed %s is external (no schedule or depends_on), skipping engine loop",
                    feed_cls.ref(),
                )

        for strategy_cls in self._strategies:
            sid = strategy_ids[strategy_cls.ref()]
            from ascent.engine.consumer import run_strategy

            t = threading.Thread(
                target=run_strategy,
                args=(sid,),
                kwargs={
                    "database_url": self._database_url,
                    "redis_url": self._redis_url,
                    "shutdown_event": shutdown_event,
                },
                name=f"strategy-{strategy_cls.__name__}",
            )
            threads.append(t)

        if self._include_writer:
            from ascent.engine.writer import run_db_writer

            t = threading.Thread(
                target=run_db_writer,
                kwargs={
                    "database_url": self._database_url,
                    "redis_url": self._redis_url,
                    "shutdown_event": shutdown_event,
                },
                name="db-writer",
            )
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Log startup banner
        self._log_banner(feed_ids, strategy_ids, threads)

        # Block until shutdown
        shutdown_event.wait()

        # Join all threads
        logger.info("Waiting for %d engine threads to finish...", len(threads))
        for t in threads:
            t.join(timeout=10.0)
            if t.is_alive():
                logger.warning("Thread %s did not shut down in time", t.name)

        logger.info("Runner shut down cleanly")

    @staticmethod
    def _heartbeat_loop(
        cache: EngineCache,
        targets: list[tuple[str, uuid.UUID]],
        shutdown_event: threading.Event,
    ) -> None:
        """Write heartbeat keys every 10s for all registered objects."""
        while not shutdown_event.is_set():
            for entity_type, entity_id in targets:
                cache.set_heartbeat(entity_type, entity_id, ttl=30)
            shutdown_event.wait(timeout=10.0)

    @staticmethod
    def _log_banner(
        feed_ids: dict[str, uuid.UUID],
        strategy_ids: dict[str, uuid.UUID],
        threads: list[threading.Thread],
    ) -> None:
        """Log a startup banner showing all running objects."""
        lines = ["", "=" * 60, "  Ascent Runner", "=" * 60]
        if feed_ids:
            lines.append("  Feeds:")
            for ref, fid in feed_ids.items():
                lines.append(f"    {ref}  ({fid})")
        if strategy_ids:
            lines.append("  Strategies:")
            for ref, sid in strategy_ids.items():
                lines.append(f"    {ref}  ({sid})")
        lines.append(f"  Threads: {len(threads)}")
        lines.append("=" * 60)
        logger.info("\n".join(lines))


def serve(
    *objects: type,
    database_url: str | None = None,
    redis_url: str | None = None,
    include_writer: bool = False,
    log_level: str = "INFO",
) -> None:
    """Run multiple feeds and/or strategies in a single process.

    Auto-deploys all objects, then starts their engine loops in threads.
    Blocks until SIGINT/SIGTERM.

    Example::

        from ascent.engine.runner import serve
        serve(MarketData, OUParams, PairsStrategy)
    """
    runner = Runner(
        database_url=database_url,
        redis_url=redis_url,
        include_writer=include_writer,
        log_level=log_level,
    )
    for obj in objects:
        runner.add(obj)
    runner.run()
