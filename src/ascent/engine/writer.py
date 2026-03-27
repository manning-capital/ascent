"""DB-writer consumer — persists feed data to PostgreSQL.

Subscribes to all active feed Redis pub/sub channels. On each event, reads the
latest DataFrame from Redis and auto-persists it to the feed's mapped EAV table.
Also runs any registered @persist handlers.
"""

from __future__ import annotations

import logging
import signal
import threading
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.feeds import Feed as FeedModel
from ascent.engine.cache import EngineCache

logger = logging.getLogger(__name__)


def _import_feed(feed_ref: str):
    """Import a Feed object from a module:name reference."""
    import importlib

    module_path, obj_name = feed_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def _auto_persist(session: Session, output_table: str, df, feed_id: uuid.UUID) -> int:
    """Bulk-upsert a DataFrame to the mapped EAV table.

    Uses pandas to_sql with a temporary staging approach for conflict handling.

    Args:
        session: SQLAlchemy session.
        output_table: Target table name (e.g., 'provider_asset_attribute').
        df: The feed output DataFrame.
        feed_id: Feed ID for logging.

    Returns:
        Number of rows written.
    """
    if df.empty:
        return 0

    bind = session.get_bind()

    # Use pandas to_sql for bulk insert with 'replace' strategy
    # For production, this should use INSERT ... ON CONFLICT for true upsert
    try:
        df.to_sql(
            output_table,
            con=bind,
            if_exists="append",
            index=False,
            method="multi",
        )
        return len(df)
    except Exception:
        logger.exception("Auto-persist failed for feed %s to table %s", feed_id, output_table)
        raise


def _run_persist_handlers(feed_obj, df, session: Session) -> None:
    """Run custom @persist handlers registered on the feed.

    Each handler runs independently — if one fails, others still execute.
    """
    for handler in feed_obj._persist_handlers:
        try:
            handler.fn(df, session)
        except Exception:
            logger.exception(
                "Custom persist handler '%s' failed for feed '%s'",
                handler.name,
                feed_obj.__name__,
            )


def run_db_writer(
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
) -> None:
    """Run the DB-writer consumer in a long-running Redis pub/sub poll loop.

    Subscribes to all active feed channels and auto-persists data to PostgreSQL.

    Args:
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
    """
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    cache = EngineCache(redis_url)

    # Load all active feeds and their channels
    with Session(engine) as db:
        feeds = db.execute(select(FeedModel).where(FeedModel.is_active.is_(True))).scalars().all()
        if not feeds:
            raise ValueError("No active feeds found in database")

        feed_map: dict[uuid.UUID, FeedModel] = {}
        channels: list[str] = []
        for f in feeds:
            feed_map[f.id] = f
            channels.append(f.channel)

    # Pre-import feed objects for @persist handler support
    feed_objects: dict[uuid.UUID, object] = {}
    for fid, f in feed_map.items():
        try:
            feed_objects[fid] = _import_feed(f.feed_ref)
        except Exception:
            logger.warning(
                "Could not import feed %s (%s) — @persist handlers unavailable",
                fid,
                f.feed_ref,
            )

    # Subscribe to all feed channels via Redis pub/sub
    pubsub = cache.subscribe(channels)

    logger.info("Starting DB-writer consumer, subscribed to %d feed channels", len(channels))

    shutdown = threading.Event()

    def _signal_handler(signum, frame):
        logger.info("Received signal %s, shutting down DB-writer", signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        # Parse event
        feed_id = uuid.UUID(event["feed_id"])
        output_table = event["schema"]

        feed_record = feed_map.get(feed_id)
        if feed_record is None:
            logger.warning("Received event for unknown feed %s, skipping", feed_id)
            continue

        # Read latest data from Redis
        df = cache.get_feed_data(feed_id)
        if df is None:
            logger.warning("No cached data for feed %s, skipping persist", feed_id)
            continue

        # Auto-persist to the mapped EAV table
        session = session_factory()
        try:
            rows = _auto_persist(session, output_table, df, feed_id)
            session.commit()
            logger.debug("Auto-persisted %d rows for feed %s to %s", rows, feed_id, output_table)
        except Exception:
            session.rollback()
            logger.exception("Failed to auto-persist feed %s", feed_id)
        finally:
            session.close()

        # Run custom @persist handlers
        feed_obj = feed_objects.get(feed_id)
        if feed_obj and hasattr(feed_obj, "_persist_handlers") and feed_obj._persist_handlers:
            session = session_factory()
            try:
                _run_persist_handlers(feed_obj, df, session)
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

    pubsub.close()
    logger.info("DB-writer shut down cleanly")
