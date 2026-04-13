"""Strategy consumer — long-running process that evaluates strategies on feed events.

Subscribes to Redis pub/sub channels for the strategy's declared feeds. On each
feed event, reads the latest data from Redis, checks trigger logic, builds a
StrategyContext, and invokes the strategy function.
"""

from __future__ import annotations

import logging
import signal
import threading
import uuid
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.feeds import Feed as FeedModel
from ascent.database.models.feeds import StrategyFeed
from ascent.database.models.strategy import Strategy as StrategyModel
from ascent.database.models.strategy import StrategyRun
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
from ascent.engine.cache import EngineCache
from ascent.engine.context import StrategyContext, _current_context, _current_logger
from ascent.engine.tracker import RunTracker
from ascent.engine.trigger import should_evaluate

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _import_strategy(strategy_ref: str):
    """Import a strategy object from a module:name reference."""
    import importlib

    module_path, obj_name = strategy_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def _build_strategy_context(
    strategy_feeds: list[StrategyFeed],
    latest_data: dict[uuid.UUID, pd.DataFrame],
    cache: EngineCache,
    strategy_id: uuid.UUID,
) -> StrategyContext:
    """Build a StrategyContext from cached feed data and instrument state.

    Args:
        strategy_feeds: The strategy's feed associations.
        latest_data: Map of feed_id → latest DataFrame from Redis.
        cache: The engine cache for instrument state.
        strategy_id: The strategy's database ID.

    Returns:
        A fully populated StrategyContext.
    """
    # Build feed frames dict (feed_id → DataFrame)
    feed_frames: dict[uuid.UUID, pd.DataFrame] = {}
    for sf in strategy_feeds:
        df = latest_data.get(sf.feed_id)
        if df is not None:
            feed_frames[sf.feed_id] = df

    # Load instrument and composite state from Redis
    cached_state = cache.get_strategy_state(strategy_id)

    if cached_state and "instruments" in cached_state:
        instruments_data = cached_state["instruments"]
        instruments_df = pd.DataFrame.from_dict(instruments_data, orient="index")
        instruments_df.index = instruments_df.index.astype(int)
        instruments_df.index.name = "instrument_id"
    else:
        instruments_df = pd.DataFrame(columns=["state", "trade_id"])
        instruments_df.index.name = "instrument_id"

    if cached_state and "composites" in cached_state:
        composites_data = cached_state["composites"]
        composites_df = pd.DataFrame.from_dict(composites_data, orient="index")
        composites_df.index = composites_df.index.astype(int)
        composites_df.index.name = "composite_id"
    else:
        composites_df = pd.DataFrame(columns=["state", "trade_id", "member_instrument_ids"])
        composites_df.index.name = "composite_id"

    return StrategyContext(
        instruments=instruments_df, composites=composites_df, feed_frames=feed_frames
    )


def _cold_start_feeds(
    strategy_feeds: list[StrategyFeed],
    feed_records: dict[uuid.UUID, FeedModel],
    cache: EngineCache,
    latest_data: dict[uuid.UUID, pd.DataFrame],
) -> None:
    """Ensure all feeds have cached data, cold-starting from DB if needed."""
    for sf in strategy_feeds:
        feed_id = sf.feed_id
        if feed_id in latest_data:
            continue

        df = cache.get_feed_data(feed_id)
        if df is not None:
            latest_data[feed_id] = df
            logger.debug("Feed %s loaded from Redis cache", feed_id)
        else:
            feed_record = feed_records.get(feed_id)
            if feed_record:
                logger.info(
                    "Feed %s (%s) cache is cold — will populate on first event",
                    feed_id,
                    feed_record.name,
                )


def _record_feed_run_links(
    session_factory: sessionmaker,
    strategy_run_id: uuid.UUID,
    strategy_feeds: list[StrategyFeed],
    latest_feed_run_ids: dict[uuid.UUID, uuid.UUID],
    trigger_feed_id: uuid.UUID,
) -> None:
    """Insert StrategyRunFeedRun records linking this run to its active feed runs."""
    session = session_factory()
    try:
        for sf in strategy_feeds:
            feed_run_id = latest_feed_run_ids.get(sf.feed_id)
            if feed_run_id is not None:
                link = StrategyRunFeedRun(
                    strategy_run_id=strategy_run_id,
                    feed_run_id=feed_run_id,
                    feed_id=sf.feed_id,
                    is_trigger=(sf.feed_id == trigger_feed_id),
                )
                session.add(link)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("Failed to record feed run links for strategy run %s", strategy_run_id)
    finally:
        session.close()


def run_strategy(
    strategy_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
    shutdown_event: threading.Event | None = None,
) -> None:
    """Run a strategy consumer in a long-running Redis pub/sub poll loop.

    Args:
        strategy_id: The database ID of the strategy to run.
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
    """
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)

    # Load strategy and feed associations from DB
    with Session(engine) as db:
        strategy_record = db.get(StrategyModel, strategy_id)
        if strategy_record is None:
            raise ValueError(f"Strategy {strategy_id} not found in database")

        strategy_ref = strategy_record.strategy_ref
        parameters = strategy_record.parameters or {}

        strategy_feeds = (
            db.execute(
                select(StrategyFeed)
                .where(StrategyFeed.strategy_id == strategy_id)
                .order_by(StrategyFeed.order)
            )
            .scalars()
            .all()
        )

        if not strategy_feeds:
            raise ValueError(f"Strategy {strategy_id} has no linked feeds")

        # Load feed records for channel subscription
        feed_records: dict[uuid.UUID, FeedModel] = {}
        channels: list[str] = []
        for sf in strategy_feeds:
            feed_record = db.get(FeedModel, sf.feed_id)
            if feed_record:
                feed_records[sf.feed_id] = feed_record
                channels.append(feed_record.channel)

    # Import the decorated strategy function
    strategy_obj = _import_strategy(strategy_ref)

    # In-memory latest data from feeds
    latest_data: dict[uuid.UUID, pd.DataFrame] = {}
    latest_feed_run_ids: dict[uuid.UUID, uuid.UUID] = {}

    # Cold start: load existing feed data from Redis
    _cold_start_feeds(strategy_feeds, feed_records, cache, latest_data)

    # Subscribe to feed channels via Redis pub/sub
    pubsub = cache.subscribe(channels)

    logger.info(
        "Starting strategy %s (%s), subscribed to %d feed channels",
        strategy_id,
        strategy_ref,
        len(channels),
    )

    shutdown = shutdown_event or threading.Event()

    if shutdown_event is None:

        def _signal_handler(signum, frame):
            logger.info("Received signal %s, shutting down strategy %s", signum, strategy_id)
            shutdown.set()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        # Parse event
        updated_feed_id = uuid.UUID(event["feed_id"])
        raw_feed_run_id = event.get("feed_run_id")
        updated_feed_run_id = uuid.UUID(raw_feed_run_id) if raw_feed_run_id is not None else None

        # Read latest data from Redis
        df = cache.get_feed_data(updated_feed_id)
        if df is not None:
            latest_data[updated_feed_id] = df
            if updated_feed_run_id is not None:
                latest_feed_run_ids[updated_feed_id] = updated_feed_run_id

        # Check trigger logic
        if not should_evaluate(updated_feed_id, strategy_feeds, latest_data):
            continue

        logger.debug("Strategy %s triggered by feed %s", strategy_id, updated_feed_id)

        tracker = RunTracker(
            session_factory=session_factory,
            run_type="strategy",
            run_model_class=StrategyRun,
            parent_id_field="strategy_id",
            parent_id=strategy_id,
        )

        with tracker as run_logger:
            # Record which feed runs were active for this strategy run
            _record_feed_run_links(
                session_factory,
                strategy_run_id=tracker.run_id,
                strategy_feeds=strategy_feeds,
                latest_feed_run_ids=latest_feed_run_ids,
                trigger_feed_id=updated_feed_id,
            )

            token_logger = _current_logger.set(run_logger)
            try:
                # Build vectorized context
                ctx = _build_strategy_context(strategy_feeds, latest_data, cache, strategy_id)
                token_ctx = _current_context.set(ctx)

                try:
                    run_logger.info(
                        "Evaluating strategy %s (trigger: feed %s)",
                        strategy_ref,
                        updated_feed_id,
                    )
                    strategy_obj(**parameters)

                    # Persist updated instrument and composite states to Redis
                    state_data: dict = {}
                    if not ctx.instruments.empty:
                        state_data["instruments"] = ctx.instruments.to_dict(orient="index")
                    if not ctx.composites.empty:
                        state_data["composites"] = ctx.composites.to_dict(orient="index")
                    if state_data:
                        cache.set_strategy_state(strategy_id, state_data)

                    run_logger.info("Strategy %s evaluation complete", strategy_ref)
                finally:
                    _current_context.reset(token_ctx)
            finally:
                _current_logger.reset(token_logger)

    pubsub.close()
    logger.info("Strategy %s shut down cleanly", strategy_id)
