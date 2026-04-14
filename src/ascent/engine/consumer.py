"""Strategy consumer — long-running process that evaluates strategies on feed events.

Subscribes to Redis pub/sub channels for the strategy's declared feeds. On each
feed event, reads the latest data from Redis, checks trigger logic, builds a
consolidated context DataFrame, and passes it to ``strategy.evaluate(ctx)``.
"""

from __future__ import annotations

import logging
import signal
import threading
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.exchanges import Exchange as ExchangeModel
from ascent.database.models.feeds import Feed as FeedModel
from ascent.database.models.feeds import StrategyFeed
from ascent.database.models.strategy import Strategy as StrategyModel
from ascent.database.models.strategy import StrategyExchange, StrategyRun
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
from ascent.engine.cache import EngineCache
from ascent.engine.context import _current_logger
from ascent.engine.tracker import RunTracker
from ascent.engine.trade_router import TradeRouter
from ascent.engine.trigger import should_evaluate
from ascent.engine.type_cache import TypeCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trade column names (used in the MultiIndex column level 1)
# ---------------------------------------------------------------------------

_TRADE_FIELDS = [
    "status",
    "trade_id",
    "direction",
    "entry_price",
    "quantity",
    "unrealized_pnl",
    "entry_at",
    "order_status",
    "filled_quantity",
]


def _import_strategy(strategy_ref: str):
    """Import a strategy object from a module:name reference."""
    import importlib

    module_path, obj_name = strategy_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


# ---------------------------------------------------------------------------
# Context DataFrame builder
# ---------------------------------------------------------------------------


def _build_context_dataframe(
    strategy_feeds: list[StrategyFeed],
    latest_data: dict[uuid.UUID, pd.DataFrame],
    feed_records: dict[uuid.UUID, FeedModel],
    feed_ref_map: dict[uuid.UUID, str],
    type_cache: TypeCache,
    session_factory: sessionmaker,
    strategy_id: uuid.UUID,
) -> pd.DataFrame:
    """Build a consolidated context DataFrame for strategy evaluation.

    The returned DataFrame has:
    - **Index**: ``instrument_id`` (instrument strategies) or
      ``(composite_id, instrument_id)`` MultiIndex (composite strategies).
    - **Columns**: Two-level MultiIndex. Level 0 = group name
      (``'trade'`` or a feed name like ``'market_data'``),
      level 1 = field name (``'status'``, ``'close'``, etc.).

    Trade columns come from DB queries on active trades.
    Feed columns are pivoted from EAV format using the attribute name cache.
    """
    # ----- 1. Determine scope and collect entity IDs from feed data -----
    is_composite = False
    instrument_ids: set = set()
    composite_ids: set = set()

    for sf in strategy_feeds:
        feed_record = feed_records.get(sf.feed_id)
        df = latest_data.get(sf.feed_id)

        # Determine scope from DB model
        if feed_record and feed_record.composite_type_id is not None:
            is_composite = True
            if df is not None and not df.empty and "composite_id" in df.columns:
                composite_ids.update(df["composite_id"].unique())
        elif df is not None and not df.empty and "instrument_id" in df.columns:
            instrument_ids.update(df["instrument_id"].unique())

    # ----- 2. For composite scope, look up member instruments -----
    composite_members: dict = {}  # composite_id → [instrument_id, ...]
    if is_composite and composite_ids:
        from ascent.database.models.composites import CompositeMember

        with Session(bind=session_factory.kw["bind"]) as db:
            members = (
                db.execute(
                    select(CompositeMember)
                    .where(CompositeMember.composite_id.in_(list(composite_ids)))
                    .order_by(CompositeMember.composite_id, CompositeMember.order)
                )
                .scalars()
                .all()
            )
            for m in members:
                composite_members.setdefault(m.composite_id, []).append(m.instrument_id)
                instrument_ids.add(m.instrument_id)

    # ----- 3. Build the index -----
    if is_composite:
        index_tuples = []
        for comp_id in sorted(composite_ids):
            for inst_id in composite_members.get(comp_id, []):
                index_tuples.append((comp_id, inst_id))
        if not index_tuples:
            return pd.DataFrame()
        index = pd.MultiIndex.from_tuples(index_tuples, names=["composite_id", "instrument_id"])
    else:
        if not instrument_ids:
            return pd.DataFrame()
        index = pd.Index(sorted(instrument_ids), name="instrument_id")

    # ----- 4. Build trade columns -----
    trade_df = _build_trade_columns(
        index, is_composite, composite_members, strategy_id, type_cache, session_factory
    )

    # ----- 5. Build feed columns (pivot EAV → wide) -----
    feed_dfs: list[pd.DataFrame] = []
    for sf in strategy_feeds:
        df = latest_data.get(sf.feed_id)
        if df is None or df.empty:
            continue

        feed_record = feed_records.get(sf.feed_id)
        ref = feed_ref_map.get(sf.feed_id, str(sf.feed_id))
        feed_name = ref.lower()
        is_feed_composite = feed_record is not None and feed_record.composite_type_id is not None

        feed_df = _pivot_feed(df, feed_name, index, is_composite, is_feed_composite, type_cache)
        if feed_df is not None and not feed_df.empty:
            feed_dfs.append(feed_df)

    # ----- 6. Join trade + feed columns -----
    parts = [trade_df] + feed_dfs
    return pd.concat(parts, axis=1)


def _build_trade_columns(
    index: pd.Index | pd.MultiIndex,
    is_composite: bool,
    composite_members: dict,
    strategy_id: uuid.UUID,
    type_cache: TypeCache,
    session_factory: sessionmaker,
) -> pd.DataFrame:
    """Build trade/order state columns for each instrument in the index."""
    from ascent.database.models.orders import Order, OrderStatus
    from ascent.database.models.trades import Trade, TradeLeg

    # Create MultiIndex columns under the 'trade' namespace
    pd.MultiIndex.from_tuples(
        [("trade", f) for f in _TRADE_FIELDS], names=["group", "field"]
    )

    # Initialize all rows as WAITING
    n = len(index)
    data = pd.DataFrame(
        {
            ("trade", "status"): ["WAITING"] * n,
            ("trade", "trade_id"): [None] * n,
            ("trade", "direction"): [None] * n,
            ("trade", "entry_price"): [np.nan] * n,
            ("trade", "quantity"): [np.nan] * n,
            ("trade", "unrealized_pnl"): [np.nan] * n,
            ("trade", "entry_at"): pd.array([pd.NaT] * n, dtype="datetime64[ns]"),
            ("trade", "order_status"): [None] * n,
            ("trade", "filled_quantity"): [np.nan] * n,
        },
        index=index,
    )
    data.columns = pd.MultiIndex.from_tuples(data.columns.tolist())

    # Build reverse status maps
    status_name_map = {v: k for k, v in type_cache._trade_status_types.items()}
    order_status_name_map = {v: k for k, v in type_cache._order_status_types.items()}

    # Terminal statuses to exclude
    terminal_names = {"CLOSED", "CANCELLED"}
    terminal_ids = [
        type_cache._trade_status_types[n]
        for n in terminal_names
        if n in type_cache._trade_status_types
    ]

    with Session(bind=session_factory.kw["bind"]) as db:
        # Query all non-terminal trades for this strategy
        stmt = select(Trade).where(Trade.strategy_id == strategy_id)
        if terminal_ids:
            stmt = stmt.where(Trade.current_status_type_id.notin_(terminal_ids))
        trades = db.execute(stmt).scalars().all()

        if not trades:
            return data

        # For composite scope, build reverse mapping: frozenset(inst_ids) → composite_id
        if is_composite:
            comp_member_sets: dict[frozenset, object] = {}
            for comp_id, inst_ids in composite_members.items():
                comp_member_sets[frozenset(inst_ids)] = comp_id

        for trade in trades:
            trade_status = status_name_map.get(trade.current_status_type_id, "UNKNOWN")
            trade_id_str = str(trade.id)
            entry_at = trade.entry_at

            legs = db.execute(select(TradeLeg).where(TradeLeg.trade_id == trade.id)).scalars().all()
            if not legs:
                continue

            # Get order status for each leg
            leg_order_status: dict[uuid.UUID, str] = {}
            for leg in legs:
                if leg.entry_order_id:
                    order = db.get(Order, leg.entry_order_id)
                    if order:
                        # Get latest order status
                        latest_os = (
                            db.execute(
                                select(OrderStatus)
                                .where(OrderStatus.order_id == order.id)
                                .order_by(OrderStatus.timestamp.desc())
                                .limit(1)
                            )
                            .scalars()
                            .first()
                        )
                        if latest_os:
                            leg_order_status[leg.id] = order_status_name_map.get(
                                latest_os.order_status_type_id, "UNKNOWN"
                            )

            if is_composite:
                # Match trade legs to a composite by comparing instrument sets
                # Normalize to strings for comparison since index may use str UUIDs
                leg_inst_strs = frozenset(str(leg.instrument_id) for leg in legs)
                # Also try matching against string-keyed composite member sets
                matched_comp_id = None
                for member_set, comp_id in comp_member_sets.items():
                    if frozenset(str(m) for m in member_set) == leg_inst_strs:
                        matched_comp_id = comp_id
                        break
                if matched_comp_id is None:
                    continue

                for leg in legs:
                    # Normalize instrument_id to match the index type
                    leg_inst = str(leg.instrument_id)
                    idx_key = (str(matched_comp_id), leg_inst)
                    if idx_key not in index:
                        idx_key = (matched_comp_id, leg.instrument_id)
                        if idx_key not in index:
                            continue
                    data.loc[idx_key, ("trade", "status")] = trade_status
                    data.loc[idx_key, ("trade", "trade_id")] = trade_id_str
                    data.loc[idx_key, ("trade", "direction")] = leg.direction
                    data.loc[idx_key, ("trade", "entry_price")] = (
                        leg.entry_price if leg.entry_price is not None else np.nan
                    )
                    data.loc[idx_key, ("trade", "quantity")] = (
                        leg.quantity if leg.quantity is not None else np.nan
                    )
                    data.loc[idx_key, ("trade", "entry_at")] = entry_at
                    data.loc[idx_key, ("trade", "order_status")] = leg_order_status.get(leg.id)
                    data.loc[idx_key, ("trade", "filled_quantity")] = np.nan
                    if leg.entry_order_id:
                        order = db.get(Order, leg.entry_order_id)
                        if order and order.filled_quantity is not None:
                            data.loc[idx_key, ("trade", "filled_quantity")] = order.filled_quantity
            else:
                # Instrument scope — each leg maps to one instrument row
                # Normalize instrument_id to match the index type (feed data may use strings)
                for leg in legs:
                    inst_id = str(leg.instrument_id)
                    if inst_id not in index:
                        # Try native UUID in case index uses UUID objects
                        inst_id = leg.instrument_id
                        if inst_id not in index:
                            continue
                    data.loc[inst_id, ("trade", "status")] = trade_status
                    data.loc[inst_id, ("trade", "trade_id")] = trade_id_str
                    data.loc[inst_id, ("trade", "direction")] = leg.direction
                    data.loc[inst_id, ("trade", "entry_price")] = (
                        leg.entry_price if leg.entry_price is not None else np.nan
                    )
                    data.loc[inst_id, ("trade", "quantity")] = (
                        leg.quantity if leg.quantity is not None else np.nan
                    )
                    data.loc[inst_id, ("trade", "entry_at")] = entry_at
                    data.loc[inst_id, ("trade", "order_status")] = leg_order_status.get(leg.id)
                    if leg.entry_order_id:
                        order = db.get(Order, leg.entry_order_id)
                        if order and order.filled_quantity is not None:
                            data.loc[inst_id, ("trade", "filled_quantity")] = order.filled_quantity

    return data


def _pivot_feed(
    df: pd.DataFrame,
    feed_name: str,
    index: pd.Index | pd.MultiIndex,
    is_composite: bool,
    is_feed_composite: bool,
    type_cache: TypeCache,
) -> pd.DataFrame | None:
    """Pivot a feed DataFrame from EAV to wide format and align to the context index.

    Args:
        df: Raw EAV feed data (timestamp, instrument_id/composite_id, attribute_id, attribute_value).
        feed_name: Lowercase feed name for column namespace (e.g. ``'market_data'``).
        index: The context index to align to.
        is_composite: Whether the strategy context uses composite MultiIndex.
        is_feed_composite: Whether this specific feed is composite-scoped.
        type_cache: For attribute_id → name lookups.

    Returns:
        A DataFrame with MultiIndex columns ``(feed_name, attr_name)`` aligned to the context index,
        or None if the feed has no usable data.
    """
    if "attribute_id" not in df.columns or "attribute_value" not in df.columns:
        return None

    # Determine the entity column
    if is_feed_composite and "composite_id" in df.columns:
        entity_col = "composite_id"
    elif "instrument_id" in df.columns:
        entity_col = "instrument_id"
    else:
        return None

    # Map attribute_id → name
    # Feed data may contain UUIDs (correct), UUID strings (after Redis JSON round-trip),
    # or integers (legacy placeholder). Handle all cases.
    working = df.copy()

    def _resolve_attr_name(aid):
        # Direct UUID lookup
        if aid in type_cache._attributes:
            return type_cache._attributes[aid]
        # Try parsing as UUID string (common after Redis JSON serialization)
        if isinstance(aid, str):
            try:
                parsed = uuid.UUID(aid)
                if parsed in type_cache._attributes:
                    return type_cache._attributes[parsed]
            except ValueError:
                pass
        # Fallback: use string representation
        return str(aid)

    working["attribute_name"] = working["attribute_id"].map(_resolve_attr_name)
    logger.debug(
        "Feed %s: attribute_id types=%s, sample=%s, resolved=%s",
        feed_name,
        type(working["attribute_id"].iloc[0]).__name__ if len(working) > 0 else "empty",
        list(working["attribute_id"].unique()[:5]),
        list(working["attribute_name"].unique()[:10]),
    )

    # Take the latest value per entity per attribute (in case of multiple timestamps)
    if "timestamp" in working.columns:
        working = working.sort_values("timestamp").drop_duplicates(
            subset=[entity_col, "attribute_name"], keep="last"
        )

    # Pivot: rows = entity_id, columns = attribute_name, values = attribute_value
    pivoted = working.pivot_table(
        index=entity_col,
        columns="attribute_name",
        values="attribute_value",
        aggfunc="last",
    )

    if pivoted.empty:
        return None

    # Add feed namespace to columns → MultiIndex
    pivoted.columns = pd.MultiIndex.from_tuples([(feed_name, col) for col in pivoted.columns])

    # Align to the context index
    if is_composite:
        if is_feed_composite:
            # Composite-scoped feed → join on composite_id (level 0), repeat for members
            pivoted.index.name = "composite_id"
            # Reindex to match composite_id level, then broadcast to all member rows
            comp_ids = index.get_level_values("composite_id")
            result = pivoted.reindex(comp_ids)
            result.index = index
        else:
            # Instrument-scoped feed → join on instrument_id (level 1)
            pivoted.index.name = "instrument_id"
            inst_ids = index.get_level_values("instrument_id")
            result = pivoted.reindex(inst_ids)
            result.index = index
    else:
        # Simple instrument index
        pivoted.index.name = "instrument_id"
        result = pivoted.reindex(index)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


def run_strategy(
    strategy_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
    shutdown_event: threading.Event | None = None,
    strategy_cls: type | None = None,
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

    # Always create TypeCache (needed for attribute name lookups in context builder)
    type_cache = TypeCache(session_factory)

    # Load strategy and feed associations from DB
    with Session(engine) as db:
        strategy_record = db.get(StrategyModel, strategy_id)
        if strategy_record is None:
            raise ValueError(f"Strategy {strategy_id} not found in database")

        strategy_ref = strategy_record.strategy_ref
        parameters = strategy_record.parameters or {}
        portfolio_id = strategy_record.portfolio_id

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

        # Load feed records for channel subscription and scope detection
        feed_records: dict[uuid.UUID, FeedModel] = {}
        channels: list[str] = []
        for sf in strategy_feeds:
            feed_record = db.get(FeedModel, sf.feed_id)
            if feed_record:
                feed_records[sf.feed_id] = feed_record
                channels.append(feed_record.channel)

        # Load exchange associations
        strategy_exchanges = (
            db.execute(
                select(StrategyExchange)
                .where(StrategyExchange.strategy_id == strategy_id)
                .order_by(StrategyExchange.order)
            )
            .scalars()
            .all()
        )
        exchange_map: dict[uuid.UUID, dict] = {}
        for se in strategy_exchanges:
            exchange_record = db.get(ExchangeModel, se.exchange_id)
            if exchange_record and exchange_record.is_active:
                exchange_map[exchange_record.id] = {
                    "name": exchange_record.name,
                    "channel": f"ascent.exchange.{exchange_record.id}",
                    "is_active": exchange_record.is_active,
                    "instrument_type_id": exchange_record.instrument_type_id,
                    "provider_id": exchange_record.provider_id,
                }

    # Use provided strategy class, or fall back to import via ref
    if strategy_cls is None:
        strategy_cls = _import_strategy(strategy_ref)
    strategy_instance = strategy_cls(parameters)

    # Wire up trade router if exchanges are configured
    if exchange_map:
        strategy_instance._trade_router = TradeRouter(
            cache=cache,
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            exchange_map=exchange_map,
            session_factory=session_factory,
            type_cache=type_cache,
        )
        logger.info(
            "Trade router configured with %d exchange(s): %s",
            len(exchange_map),
            ", ".join(info["name"] for info in exchange_map.values()),
        )

    # Build feed ref mapping: feed_id → feed_ref string
    feed_ref_map: dict[uuid.UUID, str] = {}
    for fid, fr in feed_records.items():
        feed_ref_map[fid] = fr.feed_ref

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

            # Update trade router with current run ID
            if strategy_instance._trade_router is not None:
                strategy_instance._trade_router._strategy_run_id = tracker.run_id

            token_logger = _current_logger.set(run_logger)
            try:
                # Build consolidated context DataFrame
                ctx = _build_context_dataframe(
                    strategy_feeds,
                    latest_data,
                    feed_records,
                    feed_ref_map,
                    type_cache,
                    session_factory,
                    strategy_id,
                )

                run_logger.info(
                    "Evaluating strategy %s (trigger: feed %s, rows: %d)",
                    strategy_ref,
                    updated_feed_id,
                    len(ctx),
                )
                strategy_instance.evaluate(ctx)

                run_logger.info("Strategy %s evaluation complete", strategy_ref)
            finally:
                _current_logger.reset(token_logger)

    pubsub.close()
    logger.info("Strategy %s shut down cleanly", strategy_id)
