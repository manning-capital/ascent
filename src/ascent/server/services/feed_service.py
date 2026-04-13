"""Service layer for feed CRUD and run queries."""

import datetime
import uuid
from typing import Literal

import pandas as pd
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.orm import Session, joinedload

from ascent.database.models.feeds import Feed, FeedDependency, FeedPartition, FeedRun, StrategyFeed
from ascent.database.models.types import CompositeType, InstrumentType
from ascent.engine.cache import EngineCache
from ascent.feeds.partition import generate_keys, partition_key_for, partition_window
from ascent.feeds.schedule import Schedule
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.feeds import (
    FeedCreate,
    FeedDependencyCreate,
    FeedDependencySchema,
    FeedDetail,
    FeedListItem,
    FeedPartitionItem,
    FeedPublishResponse,
    FeedRunListItem,
    FeedUpdate,
    StrategyFeedItem,
)


def _resolve_scope(feed: Feed) -> tuple[Literal["instrument", "composite"], uuid.UUID, str | None]:
    """Derive scope_type, scope_type_id, and scope_type_name from internal DB columns."""
    if feed.instrument_type_id is not None:
        name = feed.instrument_type.display_name if feed.instrument_type else None
        return "instrument", feed.instrument_type_id, name
    name = feed.composite_type.display_name if feed.composite_type else None
    return "composite", feed.composite_type_id, name  # type: ignore[return-value]


def _scope_to_db_columns(scope_type: str, scope_type_id: uuid.UUID) -> dict[str, uuid.UUID | None]:
    """Translate API scope_type/scope_type_id to internal DB column values."""
    if scope_type == "instrument":
        return {"instrument_type_id": scope_type_id, "composite_type_id": None}
    return {"instrument_type_id": None, "composite_type_id": scope_type_id}


_INSTRUMENT_OUTPUT_TABLES = {"instrument_attribute", "instrument_period_attribute"}
_COMPOSITE_OUTPUT_TABLES = {"composite_attribute", "composite_period_attribute"}


def _validate_scope_type_id(db: Session, scope_type: str, scope_type_id: uuid.UUID) -> None:
    """Verify the scope_type_id exists in the appropriate type table."""
    if scope_type == "instrument":
        if not db.get(InstrumentType, scope_type_id):
            raise BadRequestError(f"Instrument type {scope_type_id} not found")
    else:
        if not db.get(CompositeType, scope_type_id):
            raise BadRequestError(f"Composite type {scope_type_id} not found")


def _validate_output_table(scope_type: str, output_table: str) -> None:
    """Verify output_table is consistent with scope_type."""
    if scope_type == "instrument" and output_table in _COMPOSITE_OUTPUT_TABLES:
        raise BadRequestError(
            f"Instrument-scoped feed cannot use composite output table '{output_table}'"
        )
    if scope_type == "composite" and output_table in _INSTRUMENT_OUTPUT_TABLES:
        raise BadRequestError(
            f"Composite-scoped feed cannot use instrument output table '{output_table}'"
        )


def _build_feed_list_item(
    feed: Feed,
    total_runs: int,
    last_run: FeedRun | None,
    connection_status: str = "disconnected",
) -> FeedListItem:
    """Build a FeedListItem from a Feed ORM object with scope translation."""
    scope_type, scope_type_id, scope_type_name = _resolve_scope(feed)
    return FeedListItem(
        id=feed.id,
        name=feed.name,
        display_name=feed.display_name,
        description=feed.description,
        feed_type_id=feed.feed_type_id,
        provider_id=feed.provider_id,
        provider_name=feed.provider.name if feed.provider else None,
        scope_type=scope_type,
        scope_type_id=scope_type_id,
        scope_type_name=scope_type_name,
        feed_ref=feed.feed_ref,
        output_table=feed.output_table,
        schedule=feed.schedule,
        channel=feed.channel,
        is_active=feed.is_active,
        connection_status=connection_status,
        total_runs=total_runs,
        last_run_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
    )


FEED_SORT_COLUMNS = {
    "display_name": Feed.display_name,
    "channel": Feed.channel,
    "is_active": Feed.is_active,
}


def get_feeds(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "display_name",
    sort_order: str = "asc",
    cache: EngineCache | None = None,
) -> tuple[list[FeedListItem], int]:
    conditions = []
    if search:
        conditions.append(
            Feed.display_name.ilike(f"%{search}%") | Feed.channel.ilike(f"%{search}%")
        )
    if is_active is not None:
        conditions.append(Feed.is_active == is_active)

    count_q = select(func.count()).select_from(Feed)
    if conditions:
        count_q = count_q.where(*conditions)
    total = db.execute(count_q).scalar() or 0

    query = select(Feed).options(
        joinedload(Feed.provider),
        joinedload(Feed.instrument_type),
        joinedload(Feed.composite_type),
    )
    if conditions:
        query = query.where(*conditions)

    sort_col = FEED_SORT_COLUMNS.get(sort_field, Feed.display_name)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    feeds = (
        db.execute(query.order_by(sort_expr).offset((page - 1) * page_size).limit(page_size))
        .unique()
        .scalars()
        .all()
    )

    # Batch-query heartbeat statuses if cache is available
    feed_ids = [f.id for f in feeds]
    heartbeat_map: dict[uuid.UUID, bool] = {}
    if cache is not None and feed_ids:
        heartbeat_map = cache.get_connection_statuses("feed", feed_ids)

    items = []
    for f in feeds:
        # Compute run stats
        total_runs = (
            db.execute(
                select(func.count()).select_from(FeedRun).where(FeedRun.feed_id == f.id)
            ).scalar()
            or 0
        )
        last_run = (
            db.execute(
                select(FeedRun)
                .where(FeedRun.feed_id == f.id)
                .order_by(FeedRun.started_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        conn_status = "connected" if heartbeat_map.get(f.id, False) else "disconnected"
        items.append(_build_feed_list_item(f, total_runs, last_run, conn_status))
    return items, total


def get_feed_detail(
    db: Session, feed_id: uuid.UUID, cache: EngineCache | None = None
) -> FeedDetail:
    query = (
        select(Feed)
        .options(
            joinedload(Feed.provider),
            joinedload(Feed.instrument_type),
            joinedload(Feed.composite_type),
        )
        .where(Feed.id == feed_id)
    )
    feed = db.execute(query).unique().scalar_one_or_none()
    if not feed:
        raise NotFoundError("Feed not found")

    total_runs = (
        db.execute(
            select(func.count()).select_from(FeedRun).where(FeedRun.feed_id == feed_id)
        ).scalar()
        or 0
    )
    last_run = (
        db.execute(
            select(FeedRun)
            .where(FeedRun.feed_id == feed_id)
            .order_by(FeedRun.started_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    scope_type, scope_type_id, scope_type_name = _resolve_scope(feed)

    return FeedDetail(
        id=feed.id,
        name=feed.name,
        display_name=feed.display_name,
        description=feed.description,
        feed_type_id=feed.feed_type_id,
        provider_id=feed.provider_id,
        provider_name=feed.provider.name if feed.provider else None,
        scope_type=scope_type,
        scope_type_id=scope_type_id,
        scope_type_name=scope_type_name,
        feed_ref=feed.feed_ref,
        output_table=feed.output_table,
        schedule=feed.schedule,
        channel=feed.channel,
        is_active=feed.is_active,
        connection_status=(
            "connected"
            if cache is not None and cache.is_connected("feed", feed_id)
            else "disconnected"
        ),
        parameters=feed.parameters,
        parameter_schema=feed.parameter_schema,
        data_schema=feed.data_schema,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
        total_runs=total_runs,
        last_run_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
    )


def create_feed(db: Session, data: FeedCreate) -> Feed:
    _validate_scope_type_id(db, data.scope_type, data.scope_type_id)
    _validate_output_table(data.scope_type, data.output_table)
    db_columns = _scope_to_db_columns(data.scope_type, data.scope_type_id)
    feed_data = data.model_dump(exclude={"scope_type", "scope_type_id"})
    feed_data.update(db_columns)
    feed = Feed(**feed_data)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


def update_feed(db: Session, feed_id: uuid.UUID, data: FeedUpdate) -> Feed:
    feed = db.get(Feed, feed_id)
    if not feed:
        raise NotFoundError("Feed not found")
    updates = data.model_dump(exclude_unset=True)
    scope_type = updates.pop("scope_type", None)
    scope_type_id = updates.pop("scope_type_id", None)
    if scope_type is not None or scope_type_id is not None:
        resolved_type = scope_type or ("instrument" if feed.instrument_type_id else "composite")
        resolved_id = scope_type_id or feed.instrument_type_id or feed.composite_type_id
        _validate_scope_type_id(db, resolved_type, resolved_id)
        output_table = updates.get("output_table", feed.output_table)
        _validate_output_table(resolved_type, output_table)
        db_columns = _scope_to_db_columns(resolved_type, resolved_id)
        updates.update(db_columns)
    elif "output_table" in updates:
        current_scope = "instrument" if feed.instrument_type_id else "composite"
        _validate_output_table(current_scope, updates["output_table"])
    for key, value in updates.items():
        setattr(feed, key, value)
    db.commit()
    db.refresh(feed)
    return feed


def delete_feed(db: Session, feed_id: uuid.UUID) -> None:
    feed = db.get(Feed, feed_id)
    if not feed:
        raise NotFoundError("Feed not found")
    db.delete(feed)
    db.commit()


FEED_RUN_SORT_COLUMNS = {
    "status": FeedRun.status,
    "started_at": FeedRun.started_at,
    "completed_at": FeedRun.completed_at,
    "records_fetched": FeedRun.records_fetched,
}


def get_feed_runs(
    db: Session,
    feed_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
    status: str | None = None,
    sort_field: str = "started_at",
    sort_order: str = "desc",
) -> tuple[list[FeedRunListItem], int]:
    base = select(FeedRun).where(FeedRun.feed_id == feed_id)
    count_base = select(func.count()).select_from(FeedRun).where(FeedRun.feed_id == feed_id)

    if status:
        base = base.where(FeedRun.status == status)
        count_base = count_base.where(FeedRun.status == status)
    if started_after:
        dt = datetime.datetime.fromisoformat(started_after)
        base = base.where(FeedRun.started_at >= dt)
        count_base = count_base.where(FeedRun.started_at >= dt)
    if started_before:
        dt = datetime.datetime.fromisoformat(started_before)
        base = base.where(FeedRun.started_at <= dt)
        count_base = count_base.where(FeedRun.started_at <= dt)

    total = db.execute(count_base).scalar() or 0

    sort_col = FEED_RUN_SORT_COLUMNS.get(sort_field, FeedRun.started_at)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    runs = (
        db.execute(base.order_by(sort_expr).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )

    items = []
    for r in runs:
        item = FeedRunListItem.model_validate(r)
        if r.partition_id is not None and r.partition is not None:
            item.partition_key = r.partition.partition_key
        items.append(item)
    return items, total


def get_feed_run(db: Session, feed_id: uuid.UUID, run_id: uuid.UUID) -> FeedRunListItem:
    run = (
        db.execute(select(FeedRun).where(FeedRun.id == run_id, FeedRun.feed_id == feed_id))
        .scalars()
        .first()
    )
    if not run:
        raise NotFoundError("Feed run not found")
    item = FeedRunListItem.model_validate(run)
    if run.partition_id is not None and run.partition is not None:
        item.partition_key = run.partition.partition_key
    return item


def get_feed_strategy_feeds(db: Session, feed_id: uuid.UUID) -> list[StrategyFeedItem]:
    sfs = db.execute(select(StrategyFeed).where(StrategyFeed.feed_id == feed_id)).scalars().all()
    return [StrategyFeedItem.model_validate(sf) for sf in sfs]


def list_partitions(
    db: Session,
    feed_id: uuid.UUID,
    start: str | None = None,
    end: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[FeedPartitionItem], int]:
    """List partitions for a feed, merging schedule-computed keys with DB records.

    For gaps (no DB row), computed partitions are returned as PENDING with no id.
    """
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError("Feed not found")

    if feed.schedule is None:
        raise BadRequestError(f"Feed {feed_id} has no schedule — cannot compute partitions")

    schedule = Schedule(**feed.schedule)
    now = datetime.datetime.now(tz=datetime.UTC)

    range_start = datetime.datetime.fromisoformat(start) if start else schedule.start_date
    range_end = datetime.datetime.fromisoformat(end) if end else now

    # Generate all expected partition keys in the range
    all_keys = generate_keys(schedule, range_start, range_end)

    # Load existing partition records for this feed in the range
    query = select(FeedPartition).where(
        FeedPartition.feed_id == feed_id,
        FeedPartition.partition_key >= range_start,
        FeedPartition.partition_key < range_end,
    )
    db_partitions = db.execute(query).scalars().all()
    db_map: dict[datetime.datetime, FeedPartition] = {p.partition_key: p for p in db_partitions}

    # Merge: for each computed key, use DB record if exists, else synthetic PENDING
    items: list[FeedPartitionItem] = []
    for key in all_keys:
        db_part = db_map.get(key)
        if db_part is not None:
            # Get latest run for this partition
            latest_run = (
                db.execute(
                    select(FeedRun)
                    .where(FeedRun.partition_id == db_part.id)
                    .order_by(FeedRun.started_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            item = FeedPartitionItem(
                id=db_part.id,
                partition_key=db_part.partition_key,
                window_start=db_part.window_start,
                window_end=db_part.window_end,
                status=db_part.status,
                latest_run=FeedRunListItem.model_validate(latest_run) if latest_run else None,
            )
        else:
            w_start, w_end = partition_window(schedule, key)
            item = FeedPartitionItem(
                id=None,
                partition_key=key,
                window_start=w_start,
                window_end=w_end,
                status="PENDING",
                latest_run=None,
            )
        items.append(item)

    # Filter by status if requested
    if status:
        items = [i for i in items if i.status == status]

    # Sort descending by partition_key (most recent first)
    items.sort(key=lambda i: i.partition_key, reverse=True)

    total = len(items)

    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = items[start_idx:end_idx]

    return page_items, total


def publish_feed_data(
    db: Session,
    feed_id: uuid.UUID,
    records: list[dict],
    cache: EngineCache,
    partition_key: datetime.datetime | None = None,
) -> FeedPublishResponse:
    """Publish external data to a feed, writing to Redis and publishing an event.

    This mirrors the publish path used by the engine's scheduled/triggered feed
    runners, allowing external processes to push data into
    the same event pipeline.

    If ``partition_key`` is provided, the data is associated with that specific
    partition. Otherwise, the partition key is computed from the current time
    (if the feed has a schedule).
    """
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError("Feed not found")

    now = datetime.datetime.now(tz=datetime.UTC)
    timestamp = now.isoformat()

    # Build DataFrame from records.  If the caller supplied a pivoted,
    # name-based format (attribute names as columns, entity names as values)
    # it is automatically unpivoted and resolved to the EAV format expected
    # by the downstream DB-writer.
    df = pd.DataFrame(records)
    df = _resolve_pivoted_data(db, df, feed.output_table)
    records_fetched = _pivoted_row_count(df, feed.output_table)

    # Resolve partition if feed has a schedule
    partition: FeedPartition | None = None
    resolved_partition_key: datetime.datetime | None = None

    if feed.schedule is not None:
        schedule = Schedule(**feed.schedule)
        resolved_partition_key = (
            partition_key if partition_key is not None else partition_key_for(schedule, now)
        )
        w_start, w_end = partition_window(schedule, resolved_partition_key)

        # Find or create partition
        partition = (
            db.execute(
                select(FeedPartition).where(
                    FeedPartition.feed_id == feed_id,
                    FeedPartition.partition_key == resolved_partition_key,
                )
            )
            .scalars()
            .first()
        )
        if partition is None:
            partition = FeedPartition(
                feed_id=feed_id,
                partition_key=resolved_partition_key,
                window_start=w_start,
                window_end=w_end,
                status="PENDING",
            )
            db.add(partition)
            db.flush()

    # Create a FeedRun record
    feed_run = FeedRun(
        feed_id=feed_id,
        partition_id=partition.id if partition else None,
        status="COMPLETED",
        records_fetched=records_fetched,
        started_at=now,
        completed_at=now,
    )
    db.add(feed_run)

    # Mark partition as materialized
    if partition is not None:
        partition.status = "MATERIALIZED"

    db.commit()
    db.refresh(feed_run)

    # Write to Redis cache
    cache.set_feed_data(feed_id, df, timestamp)

    # Publish event via Redis pub/sub (same format as engine producer)
    event = {
        "feed_id": str(feed_id),
        "feed_ref": feed.feed_ref,
        "timestamp": timestamp,
        "schema": feed.output_table,
        "feed_run_id": str(feed_run.id),
        "partition_key": resolved_partition_key.isoformat() if resolved_partition_key else None,
    }
    cache.publish(feed.channel, event)

    return FeedPublishResponse(
        feed_run_id=feed_run.id,
        partition_id=partition.id if partition else None,
        partition_key=resolved_partition_key,
        records_count=len(df),
        timestamp=timestamp,
    )


# Mapping of output_table → resolved query configuration.
# Each config defines SELECT columns (with JOINs to resolve FK UUIDs to names),
# JOIN clauses, and ORDER BY.  timestamp is excluded from SELECT since the
# partition window already defines the time context.
_PARTITION_DATA_CONFIGS: dict[str, dict] = {
    "provider_asset_metadata": {
        "select": (
            "t.provider_id, t.asset_id, p.display_name AS provider, a.display_name AS asset, m.display_name AS metadata, t.value"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN asset a ON a.id = t.asset_id "
            "LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "p.display_name, a.display_name, m.display_name",
        "pivot": {
            "group_columns": ["provider", "asset"],
            "eav_group_columns": ["provider_id", "asset_id"],
            "pivot_column": "metadata",
            "value_column": "value",
        },
        "resolve": {
            "name_lookups": {
                "provider": {"table": "provider", "target_column": "provider_id"},
                "asset": {"table": "asset", "target_column": "asset_id"},
            },
            "descriptor_lookup": {"table": "metadata", "target_column": "metadata_id"},
            "value_column": "value",
        },
    },
    "provider_content": {
        "select": (
            "t.provider_id, p.display_name AS provider, ct.display_name AS content_type, t.content_external_code"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN content_type ct ON ct.id = t.content_type_id"
        ),
        "order": "p.display_name, ct.display_name",
    },
    "instrument_attribute": {
        "select": (
            "t.instrument_id, i.display_name AS instrument, a.display_name AS attribute, t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN instrument i ON i.id = t.instrument_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "i.display_name, a.display_name",
        "pivot": {
            "group_columns": ["instrument"],
            "eav_group_columns": ["instrument_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
    },
    "instrument_period_attribute": {
        "select": (
            "t.instrument_id, i.display_name AS instrument, pd.display_name AS period, a.display_name AS attribute, t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN instrument i ON i.id = t.instrument_id "
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "i.display_name, pd.display_name, a.display_name",
        "pivot": {
            "group_columns": ["instrument", "period"],
            "eav_group_columns": ["instrument_id", "period_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
    },
    "composite_attribute": {
        "select": (
            "t.composite_id, c.display_name AS composite, a.display_name AS attribute, t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN composite c ON c.id = t.composite_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "c.display_name, a.display_name",
        "pivot": {
            "group_columns": ["composite"],
            "eav_group_columns": ["composite_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
    },
    "composite_period_attribute": {
        "select": (
            "t.composite_id, c.display_name AS composite, pd.display_name AS period, a.display_name AS attribute, t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN composite c ON c.id = t.composite_id "
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "c.display_name, pd.display_name, a.display_name",
        "pivot": {
            "group_columns": ["composite", "period"],
            "eav_group_columns": ["composite_id", "period_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
    },
}


def _pivoted_row_count(df: pd.DataFrame, output_table: str) -> int:
    """Return the number of rows that will appear after the read-side pivot.

    For EAV tables with a pivot config this is the number of distinct group-key
    combinations.  For everything else it is simply ``len(df)``.
    """
    cfg = _PARTITION_DATA_CONFIGS.get(output_table)
    if cfg is None:
        return len(df)
    pivot_cfg = cfg.get("pivot")
    if pivot_cfg is None:
        return len(df)
    eav_cols = pivot_cfg.get("eav_group_columns")
    if eav_cols is None or not all(col in df.columns for col in eav_cols):
        return len(df)
    return df[eav_cols].drop_duplicates().shape[0]


def _lookup_names(db: Session, table: str, names: list[str]) -> dict[str, uuid.UUID]:
    """Look up name → id for a list of names in a given table."""
    stmt = text(f"SELECT id, name FROM {table} WHERE name IN :names").bindparams(
        bindparam("names", expanding=True)
    )
    result = db.execute(stmt, {"names": names})
    return {row.name: row.id for row in result}


def _resolve_pivoted_data(
    db: Session,
    df: pd.DataFrame,
    output_table: str,
) -> pd.DataFrame:
    """Translate a pivoted, name-based DataFrame to EAV format with UUIDs.

    Accepts data where entity names are used as column values (e.g.
    ``provider="Kraken"``) and attribute names appear as column headers
    (e.g. ``close_price=45235.50``).  Resolves names to FK UUIDs and melts
    the attribute columns into EAV rows suitable for the target table.

    If the DataFrame is already in EAV format (UUID columns present),
    returns it unchanged.
    """
    cfg = _PARTITION_DATA_CONFIGS.get(output_table)
    if cfg is None:
        return df

    resolve_cfg = cfg.get("resolve")
    if resolve_cfg is None:
        return df

    name_lookups = resolve_cfg["name_lookups"]

    # Detect format: if any name column is present, assume pivoted format
    if not any(col in df.columns for col in name_lookups):
        return df

    descriptor_lookup = resolve_cfg["descriptor_lookup"]
    value_column = resolve_cfg["value_column"]

    result_df = df.copy()

    # Resolve name columns → UUID columns
    for name_col, lookup in name_lookups.items():
        if name_col not in result_df.columns:
            continue
        table = lookup["table"]
        target_col = lookup["target_column"]

        unique_names = result_df[name_col].dropna().unique().tolist()
        if not unique_names:
            result_df[target_col] = None
            result_df = result_df.drop(columns=[name_col])
            continue

        name_to_id = _lookup_names(db, table, unique_names)

        unresolved = [n for n in unique_names if n not in name_to_id]
        if unresolved:
            raise BadRequestError(
                f"Could not resolve {name_col} names in '{table}' table: {unresolved}"
            )

        result_df[target_col] = result_df[name_col].map(name_to_id)
        result_df = result_df.drop(columns=[name_col])

    # Identify attribute columns (everything except timestamp and resolved FK columns)
    fixed_cols = {"timestamp"} | {lookup["target_column"] for lookup in name_lookups.values()}
    attr_cols = [col for col in result_df.columns if col not in fixed_cols]

    if not attr_cols:
        return result_df

    # Melt attribute columns into EAV rows
    id_vars = [col for col in result_df.columns if col not in attr_cols]
    melted = result_df.melt(
        id_vars=id_vars,
        value_vars=attr_cols,
        var_name="_descriptor_name",
        value_name=value_column,
    )

    # Drop rows where the value is null (attribute not present for this entity)
    melted = melted.dropna(subset=[value_column])

    # Resolve descriptor names → UUIDs
    descriptor_table = descriptor_lookup["table"]
    descriptor_target = descriptor_lookup["target_column"]
    unique_descriptors = melted["_descriptor_name"].unique().tolist()

    if unique_descriptors:
        desc_to_id = _lookup_names(db, descriptor_table, unique_descriptors)

        unresolved = [n for n in unique_descriptors if n not in desc_to_id]
        if unresolved:
            raise BadRequestError(
                f"Could not resolve descriptor names in '{descriptor_table}' table: {unresolved}"
            )

        melted[descriptor_target] = melted["_descriptor_name"].map(desc_to_id)

    melted = melted.drop(columns=["_descriptor_name"])

    return melted


def _pivot_rows(
    rows: list[dict],
    pivot_cfg: dict,
    page: int,
    page_size: int,
) -> PaginatedResponse[dict]:
    """Pivot EAV-style rows so descriptor names become columns."""
    if not rows:
        return PaginatedResponse[dict](
            items=[], total=0, page=page, page_size=page_size, total_pages=0
        )

    df = pd.DataFrame(rows)
    group_cols = pivot_cfg["group_columns"]
    eav_group_cols = pivot_cfg.get("eav_group_columns", [])
    pivot_col = pivot_cfg["pivot_column"]
    value_col = pivot_cfg["value_column"]

    # Include ID columns in the pivot index so they survive into the output
    index_cols = list(dict.fromkeys(eav_group_cols + group_cols))

    pivoted = df.pivot_table(
        index=index_cols,
        columns=pivot_col,
        values=value_col,
        aggfunc="first",
    ).reset_index()

    # Remove axis name left over from the pivot
    pivoted.columns.name = None

    pivoted = pivoted.sort_values(group_cols).reset_index(drop=True)

    total = len(pivoted)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = pivoted.iloc[start_idx:end_idx]

    # Convert to JSON-serializable dicts
    items = []
    for _, row in page_df.iterrows():
        item = {}
        for col in page_df.columns:
            val = row[col]
            if val is None or (isinstance(val, float) and val != val):
                item[col] = None
            elif hasattr(val, "item"):  # numpy scalar → Python scalar
                item[col] = val.item()
            elif isinstance(val, datetime.datetime):
                item[col] = val.isoformat()
            elif isinstance(val, uuid.UUID):
                item[col] = str(val)
            else:
                item[col] = val
        items.append(item)

    return PaginatedResponse[dict](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_partition_data(
    db: Session,
    feed_id: uuid.UUID,
    partition_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[dict]:
    """Fetch actual data rows for a feed partition from TimescaleDB.

    Queries the feed's ``output_table`` filtered to the partition's time window.
    Foreign-key UUID columns are resolved to human-readable names for known
    output tables, and the ``timestamp`` column is excluded since the partition
    window already provides the time context.

    For EAV-style attribute tables the rows are automatically pivoted so that
    descriptor names (attribute / metadata) become columns.
    """
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError("Feed not found")

    partition = db.get(FeedPartition, partition_id)
    if partition is None:
        raise NotFoundError("Partition not found")
    if partition.feed_id != feed_id:
        raise BadRequestError(f"Partition {partition_id} does not belong to feed {feed_id}")

    output_table = feed.output_table
    window_params = {
        "window_start": partition.window_start,
        "window_end": partition.window_end,
    }

    cfg = _PARTITION_DATA_CONFIGS.get(output_table)
    pivot_cfg = cfg.get("pivot") if cfg else None

    if cfg is not None and pivot_cfg is not None:
        # Fetch all rows for the partition window — pagination is applied
        # after the pivot so that page boundaries align with pivoted rows.
        data_sql = (
            f"SELECT {cfg['select']} FROM {output_table} t "
            f"{cfg['joins']} "
            "WHERE t.timestamp >= :window_start AND t.timestamp < :window_end "
            f"ORDER BY {cfg['order']}"
        )
        data_result = db.execute(text(data_sql), window_params)
        rows = [dict(row._mapping) for row in data_result]
        return _pivot_rows(rows, pivot_cfg, page, page_size)

    # Non-pivot path — paginate at the SQL level
    offset = (page - 1) * page_size

    count_result = db.execute(
        text(
            f"SELECT COUNT(*) FROM {output_table} t "
            "WHERE t.timestamp >= :window_start AND t.timestamp < :window_end"
        ),
        window_params,
    )
    total = count_result.scalar() or 0

    if cfg is not None:
        data_sql = (
            f"SELECT {cfg['select']} FROM {output_table} t "
            f"{cfg['joins']} "
            "WHERE t.timestamp >= :window_start AND t.timestamp < :window_end "
            f"ORDER BY {cfg['order']} "
            "LIMIT :limit OFFSET :offset"
        )
    else:
        # Fallback for unknown output tables — return all columns as-is
        data_sql = (
            f"SELECT * FROM {output_table} t "
            "WHERE t.timestamp >= :window_start AND t.timestamp < :window_end "
            "ORDER BY t.timestamp "
            "LIMIT :limit OFFSET :offset"
        )

    data_result = db.execute(
        text(data_sql),
        {**window_params, "limit": page_size, "offset": offset},
    )

    rows = [dict(row._mapping) for row in data_result]

    # Serialize datetime/UUID values for JSON response
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                row[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                row[key] = str(value)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse[dict](
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_feed_dependencies(db: Session, feed_id: uuid.UUID) -> list[FeedDependencySchema]:
    rows = (
        db.execute(select(FeedDependency).where(FeedDependency.feed_id == feed_id)).scalars().all()
    )
    return [FeedDependencySchema.model_validate(r) for r in rows]


def create_feed_dependency(
    db: Session, feed_id: uuid.UUID, data: FeedDependencyCreate
) -> FeedDependency:
    obj = FeedDependency(feed_id=feed_id, depends_on_feed_id=data.depends_on_feed_id)
    db.add(obj)
    db.commit()
    return obj
