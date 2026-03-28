"""Service layer for feed CRUD and run queries."""

import datetime
import uuid

import pandas as pd
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.orm import Session

from ascent.database.models.feeds import Feed, FeedPartition, FeedRun, StrategyFeed
from ascent.engine.cache import EngineCache
from ascent.feeds.partition import generate_keys, partition_key_for, partition_window
from ascent.feeds.schedule import Schedule
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.feeds import (
    FeedCreate,
    FeedDetail,
    FeedListItem,
    FeedPartitionItem,
    FeedPublishResponse,
    FeedRunListItem,
    FeedUpdate,
    StrategyFeedItem,
)


def get_feeds(db: Session) -> list[FeedListItem]:
    feeds = db.execute(select(Feed)).scalars().all()

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

        items.append(
            FeedListItem(
                id=f.id,
                name=f.name,
                description=f.description,
                feed_type_id=f.feed_type_id,
                feed_ref=f.feed_ref,
                output_table=f.output_table,
                schedule=f.schedule,
                channel=f.channel,
                is_active=f.is_active,
                total_runs=total_runs,
                last_run_at=last_run.started_at if last_run else None,
                last_run_status=last_run.status if last_run else None,
            )
        )
    return items


def get_feed_detail(db: Session, feed_id: uuid.UUID) -> FeedDetail:
    feed = db.get(Feed, feed_id)
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

    return FeedDetail(
        id=feed.id,
        name=feed.name,
        description=feed.description,
        feed_type_id=feed.feed_type_id,
        feed_ref=feed.feed_ref,
        output_table=feed.output_table,
        schedule=feed.schedule,
        channel=feed.channel,
        is_active=feed.is_active,
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
    feed = Feed(**data.model_dump())
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


def update_feed(db: Session, feed_id: uuid.UUID, data: FeedUpdate) -> Feed:
    feed = db.get(Feed, feed_id)
    if not feed:
        raise NotFoundError("Feed not found")
    for key, value in data.model_dump(exclude_unset=True).items():
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


def get_feed_runs(
    db: Session,
    feed_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
) -> tuple[list[FeedRunListItem], int]:
    base = select(FeedRun).where(FeedRun.feed_id == feed_id)
    count_base = select(func.count()).select_from(FeedRun).where(FeedRun.feed_id == feed_id)

    if started_after:
        dt = datetime.datetime.fromisoformat(started_after)
        base = base.where(FeedRun.started_at >= dt)
        count_base = count_base.where(FeedRun.started_at >= dt)
    if started_before:
        dt = datetime.datetime.fromisoformat(started_before)
        base = base.where(FeedRun.started_at <= dt)
        count_base = count_base.where(FeedRun.started_at <= dt)

    total = db.execute(count_base).scalar() or 0

    runs = (
        db.execute(
            base.order_by(FeedRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
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
    "provider_asset_attribute": {
        "select": (
            "t.provider_id, t.from_asset_id, t.to_asset_id, "
            "p.name AS provider, "
            "fa.name AS from_asset, "
            "ta.name AS to_asset, "
            "a.name AS attribute, "
            "t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN asset fa ON fa.id = t.from_asset_id "
            "LEFT JOIN asset ta ON ta.id = t.to_asset_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "p.name, fa.name, ta.name, a.name",
        "pivot": {
            "group_columns": ["provider", "from_asset", "to_asset"],
            "eav_group_columns": ["provider_id", "from_asset_id", "to_asset_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
        "resolve": {
            "name_lookups": {
                "provider": {"table": "provider", "target_column": "provider_id"},
                "from_asset": {"table": "asset", "target_column": "from_asset_id"},
                "to_asset": {"table": "asset", "target_column": "to_asset_id"},
            },
            "descriptor_lookup": {"table": "attribute", "target_column": "attribute_id"},
            "value_column": "attribute_value",
        },
    },
    "provider_asset_period_attribute": {
        "select": (
            "t.provider_id, t.from_asset_id, t.to_asset_id, t.period_id, "
            "p.name AS provider, "
            "fa.name AS from_asset, "
            "ta.name AS to_asset, "
            "pd.name AS period, "
            "a.name AS attribute, "
            "t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN asset fa ON fa.id = t.from_asset_id "
            "LEFT JOIN asset ta ON ta.id = t.to_asset_id "
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "p.name, fa.name, ta.name, pd.name, a.name",
        "pivot": {
            "group_columns": ["provider", "from_asset", "to_asset", "period"],
            "eav_group_columns": ["provider_id", "from_asset_id", "to_asset_id", "period_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
        "resolve": {
            "name_lookups": {
                "provider": {"table": "provider", "target_column": "provider_id"},
                "from_asset": {"table": "asset", "target_column": "from_asset_id"},
                "to_asset": {"table": "asset", "target_column": "to_asset_id"},
                "period": {"table": "period", "target_column": "period_id"},
            },
            "descriptor_lookup": {"table": "attribute", "target_column": "attribute_id"},
            "value_column": "attribute_value",
        },
    },
    "provider_asset_metadata": {
        "select": (
            "t.provider_id, t.asset_id, p.name AS provider, a.name AS asset, m.name AS metadata, t.value"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN asset a ON a.id = t.asset_id "
            "LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "p.name, a.name, m.name",
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
            "t.provider_id, p.name AS provider, ct.name AS content_type, t.content_external_code"
        ),
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN content_type ct ON ct.id = t.content_type_id"
        ),
        "order": "p.name, ct.name",
    },
    "provider_asset_group_attribute": {
        "select": ("t.provider_asset_group_id, a.name AS attribute, t.attribute_value"),
        "joins": ("LEFT JOIN attribute a ON a.id = t.attribute_id"),
        "order": "t.provider_asset_group_id, a.name",
        "pivot": {
            "group_columns": ["provider_asset_group_id"],
            "eav_group_columns": ["provider_asset_group_id"],
            "pivot_column": "attribute",
            "value_column": "attribute_value",
        },
    },
    "provider_asset_group_period_attribute": {
        "select": (
            "t.provider_asset_group_id, pd.name AS period, a.name AS attribute, t.attribute_value"
        ),
        "joins": (
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "t.provider_asset_group_id, pd.name, a.name",
        "pivot": {
            "group_columns": ["provider_asset_group_id", "period"],
            "eav_group_columns": ["provider_asset_group_id", "period_id"],
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
