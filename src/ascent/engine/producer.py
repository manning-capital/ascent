"""Feed producer — long-running process that executes feeds and publishes events.

Scheduled feeds are driven by AlignedTimer. Triggered feeds subscribe to parent
feeds' Redis pub/sub channels and fire when all dependencies have fresh data.
Both types write DataFrames to Redis and publish event notifications.

Each feed tick creates a partition (a discrete time window) and links the
resulting FeedRun to it.
"""

from __future__ import annotations

import datetime
import logging
import signal
import threading
import uuid
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.feeds import Feed as FeedModel
from ascent.database.models.feeds import FeedDependency, FeedPartition, FeedRun
from ascent.engine.cache import EngineCache
from ascent.engine.context import PartitionInfo, _current_feeds, _current_logger, _current_partition
from ascent.engine.timer import AlignedTimer
from ascent.engine.tracker import RunTracker
from ascent.feeds.partition import partition_key_for, partition_window
from ascent.feeds.schedule import Schedule

if TYPE_CHECKING:
    from ascent.feeds.decorator import Feed

logger = logging.getLogger(__name__)


def _import_feed(feed_ref: str) -> Feed:
    """Import a Feed object from a module:name reference."""
    import importlib

    module_path, obj_name = feed_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def _publish_event(
    cache: EngineCache,
    channel: str,
    feed_id: uuid.UUID,
    feed_ref: str,
    output_table: str,
    feed_run_id: uuid.UUID | None = None,
    partition_key: datetime.datetime | None = None,
) -> None:
    """Publish an event notification via Redis pub/sub (no data payload)."""
    event = {
        "feed_id": str(feed_id),
        "feed_ref": feed_ref,
        "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "schema": output_table,
        "feed_run_id": str(feed_run_id) if feed_run_id is not None else None,
        "partition_key": partition_key.isoformat() if partition_key is not None else None,
    }
    cache.publish(channel, event)


def _find_or_create_partition(
    session_factory: sessionmaker,
    feed_id: uuid.UUID,
    schedule: Schedule,
    tick: datetime.datetime,
) -> FeedPartition:
    """Find or create a FeedPartition for the given tick time."""
    key = partition_key_for(schedule, tick)
    w_start, w_end = partition_window(schedule, key)

    session = session_factory()
    try:
        partition = (
            session.execute(
                select(FeedPartition).where(
                    FeedPartition.feed_id == feed_id,
                    FeedPartition.partition_key == key,
                )
            )
            .scalars()
            .first()
        )
        if partition is None:
            partition = FeedPartition(
                feed_id=feed_id,
                partition_key=key,
                window_start=w_start,
                window_end=w_end,
                status="PENDING",
            )
            session.add(partition)
            session.commit()
            session.refresh(partition)
        # Detach from session so it can be used outside
        partition_id = partition.id
        partition_key_val = partition.partition_key
        partition_window_start = partition.window_start
        partition_window_end = partition.window_end
        partition_status = partition.status
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Return a detached-safe copy
    p = FeedPartition(
        id=partition_id,
        feed_id=feed_id,
        partition_key=partition_key_val,
        window_start=partition_window_start,
        window_end=partition_window_end,
        status=partition_status,
    )
    return p


def _update_partition_status(
    session_factory: sessionmaker,
    partition_id: uuid.UUID,
    status: str,
) -> None:
    """Update a FeedPartition's status."""
    session = session_factory()
    try:
        partition = session.get(FeedPartition, partition_id)
        if partition is not None:
            partition.status = status
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _cold_start_feed(
    cache: EngineCache,
    feed_id: uuid.UUID,
    output_table: str,
    session_factory: sessionmaker,
) -> None:
    """If feed cache is cold, query DB for recent data and populate Redis."""
    if cache.is_cache_warm(feed_id):
        logger.debug("Feed %s cache is warm, skipping cold start", feed_id)
        return

    logger.info("Cold-starting feed %s from table %s", feed_id, output_table)
    session = session_factory()
    try:
        session.execute(
            select("*").select_from(
                session.get_bind().dialect.identifier_preparer.quote(output_table)
            )
        )
        logger.info("Cold start for feed %s: would query %s", feed_id, output_table)
    except Exception:
        logger.warning("Cold start for feed %s failed, will populate on first tick", feed_id)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Scheduled feed runner
# ---------------------------------------------------------------------------


def run_scheduled_feed(
    feed_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
) -> None:
    """Run a scheduled feed in a long-running loop driven by AlignedTimer.

    Each tick creates a partition and links the FeedRun to it.

    Args:
        feed_id: The database ID of the feed to run.
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
    """
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)

    # Load feed record from DB
    with Session(engine) as db:
        feed_record = db.get(FeedModel, feed_id)
        if feed_record is None:
            raise ValueError(f"Feed {feed_id} not found in database")
        if feed_record.schedule is None:
            raise ValueError(f"Feed {feed_id} has no schedule (is it a triggered feed?)")

        feed_ref = feed_record.feed_ref
        channel = feed_record.channel
        output_table = feed_record.output_table
        schedule_data = feed_record.schedule
        parameters = feed_record.parameters or {}

    # Import the decorated feed function
    feed_obj = _import_feed(feed_ref)

    # Build schedule and timer
    schedule = Schedule(**schedule_data)
    timer = AlignedTimer(schedule)

    # Cold start
    _cold_start_feed(cache, feed_id, output_table, session_factory)

    logger.info(
        "Starting scheduled feed %s (%s) with interval=%ss",
        feed_id,
        feed_ref,
        schedule.interval,
    )

    # Graceful shutdown
    shutdown = threading.Event()

    def _signal_handler(signum, frame):
        logger.info("Received signal %s, shutting down feed %s", signum, feed_id)
        shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        tick = timer.wait_for_tick()
        if shutdown.is_set():
            break

        logger.debug("Feed %s tick at %s", feed_id, tick.isoformat())

        # Find or create partition for this tick
        partition = _find_or_create_partition(session_factory, feed_id, schedule, tick)

        tracker = RunTracker(
            session_factory=session_factory,
            run_type="feed",
            run_model_class=FeedRun,
            parent_id_field="feed_id",
            parent_id=feed_id,
            extra_fields={"partition_id": partition.id},
        )

        partition_info = PartitionInfo(
            key=partition.partition_key,
            window_start=partition.window_start,
            window_end=partition.window_end,
        )

        with tracker as run_logger:
            token_logger = _current_logger.set(run_logger)
            token_partition = _current_partition.set(partition_info)
            try:
                run_logger.info(
                    "Executing feed %s at %s (partition %s)",
                    feed_ref,
                    tick.isoformat(),
                    partition.partition_key,
                )

                # Execute the feed function
                df = feed_obj(**parameters)

                # Write to Redis cache
                timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()
                cache.set_feed_data(feed_id, df, timestamp)

                # Publish event via Redis pub/sub
                _publish_event(
                    cache,
                    channel,
                    feed_id,
                    feed_ref,
                    output_table,
                    feed_run_id=tracker.run_id,
                    partition_key=partition.partition_key,
                )

                # Mark partition as materialized
                _update_partition_status(session_factory, partition.id, "MATERIALIZED")

                run_logger.info("Feed %s produced %d rows", feed_ref, len(df))
            except Exception:
                # Mark partition as failed
                _update_partition_status(session_factory, partition.id, "FAILED")
                raise
            finally:
                _current_logger.reset(token_logger)
                _current_partition.reset(token_partition)

    logger.info("Feed %s shut down cleanly", feed_id)


# ---------------------------------------------------------------------------
# Triggered feed runner
# ---------------------------------------------------------------------------


def run_triggered_feed(
    feed_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
) -> None:
    """Run a triggered feed that fires when all parent feeds have fresh data.

    Subscribes to parent feeds' Redis pub/sub channels and maintains an
    in-memory dict of latest parent data. Fires when all dependencies are
    satisfied. The partition schedule is inherited from the finest-grained parent.

    Args:
        feed_id: The database ID of the triggered feed.
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
    """
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)

    # Load feed record and dependencies
    with Session(engine) as db:
        feed_record = db.get(FeedModel, feed_id)
        if feed_record is None:
            raise ValueError(f"Feed {feed_id} not found in database")
        if feed_record.schedule is not None:
            raise ValueError(f"Feed {feed_id} has a schedule (use run_scheduled_feed)")

        feed_ref = feed_record.feed_ref
        channel = feed_record.channel
        output_table = feed_record.output_table
        parameters = feed_record.parameters or {}

        # Load parent feed info and their schedules
        deps = (
            db.execute(select(FeedDependency).where(FeedDependency.feed_id == feed_id))
            .scalars()
            .all()
        )
        parent_feeds = {}
        parent_channels = []
        parent_schedules: dict[uuid.UUID, Schedule | None] = {}
        for dep in deps:
            parent = db.get(FeedModel, dep.depends_on_feed_id)
            if parent:
                parent_feeds[parent.id] = parent
                parent_channels.append(parent.channel)
                parent_schedules[parent.id] = (
                    Schedule(**parent.schedule) if parent.schedule else None
                )

    if not parent_feeds:
        raise ValueError(f"Triggered feed {feed_id} has no parent dependencies")

    # Derive effective schedule from finest-grained parent (smallest interval)
    effective_schedule: Schedule | None = None
    for s in parent_schedules.values():
        if s is not None:
            if effective_schedule is None or s.interval < effective_schedule.interval:
                effective_schedule = s

    # Import the decorated feed function
    feed_obj = _import_feed(feed_ref)

    # Track which parents have fresh data since last run
    fresh_parents: dict[uuid.UUID, pd.DataFrame] = {}
    parent_ids = set(parent_feeds.keys())

    # Track latest partition key from parent events
    latest_parent_partition_key: datetime.datetime | None = None

    # Subscribe to all parent channels via Redis pub/sub
    pubsub = cache.subscribe(parent_channels)

    logger.info(
        "Starting triggered feed %s (%s), watching %d parent feeds (effective interval: %s)",
        feed_id,
        feed_ref,
        len(parent_feeds),
        f"{effective_schedule.interval}s" if effective_schedule else "none",
    )

    shutdown = threading.Event()

    def _signal_handler(signum, frame):
        logger.info("Received signal %s, shutting down triggered feed %s", signum, feed_id)
        shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        # Parse the event
        parent_feed_id = uuid.UUID(event["feed_id"])

        if parent_feed_id not in parent_ids:
            continue

        # Track partition key from parent event
        if event.get("partition_key"):
            latest_parent_partition_key = datetime.datetime.fromisoformat(event["partition_key"])

        # Read parent's latest data from Redis
        parent_df = cache.get_feed_data(parent_feed_id)
        if parent_df is not None:
            fresh_parents[parent_feed_id] = parent_df

        # Check if all dependencies are satisfied (AND logic)
        if not parent_ids.issubset(fresh_parents.keys()):
            continue

        logger.debug("All parents ready for triggered feed %s, executing", feed_id)

        # Create partition if we have a schedule
        partition: FeedPartition | None = None
        partition_info: PartitionInfo | None = None
        if effective_schedule is not None and latest_parent_partition_key is not None:
            partition = _find_or_create_partition(
                session_factory, feed_id, effective_schedule, latest_parent_partition_key
            )
            partition_info = PartitionInfo(
                key=partition.partition_key,
                window_start=partition.window_start,
                window_end=partition.window_end,
            )

        tracker = RunTracker(
            session_factory=session_factory,
            run_type="feed",
            run_model_class=FeedRun,
            parent_id_field="feed_id",
            parent_id=feed_id,
            extra_fields={"partition_id": partition.id} if partition else {},
        )

        with tracker as run_logger:
            # Set contextvars for get_logger() and get_feed()
            feed_data = {}
            for pid, pdf in fresh_parents.items():
                feed_data[pid] = pdf

            token_feeds = _current_feeds.set(feed_data)
            token_logger = _current_logger.set(run_logger)
            token_partition = _current_partition.set(partition_info) if partition_info else None
            try:
                run_logger.info("Executing triggered feed %s", feed_ref)
                df = feed_obj(**parameters)

                timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()
                cache.set_feed_data(feed_id, df, timestamp)
                _publish_event(
                    cache,
                    channel,
                    feed_id,
                    feed_ref,
                    output_table,
                    feed_run_id=tracker.run_id,
                    partition_key=partition.partition_key if partition else None,
                )

                if partition:
                    _update_partition_status(session_factory, partition.id, "MATERIALIZED")

                run_logger.info("Triggered feed %s produced %d rows", feed_ref, len(df))
            except Exception:
                if partition:
                    _update_partition_status(session_factory, partition.id, "FAILED")
                raise
            finally:
                _current_feeds.reset(token_feeds)
                _current_logger.reset(token_logger)
                if token_partition is not None:
                    _current_partition.reset(token_partition)

        # Reset fresh parents after firing
        fresh_parents.clear()

    pubsub.close()
    logger.info("Triggered feed %s shut down cleanly", feed_id)
