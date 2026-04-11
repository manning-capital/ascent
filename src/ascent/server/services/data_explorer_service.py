"""Service for the Data Explorer — generic querying of time-series tables."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ascent.server.exceptions import BadRequestError
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.data_explorer import (
    DataExplorerFilterOptions,
    DataSourceInfo,
    FilterOption,
)

# ---------------------------------------------------------------------------
# Config: one entry per queryable table
# ---------------------------------------------------------------------------

_DATA_EXPLORER_CONFIGS: dict[str, dict] = {
    "instrument_attribute": {
        "label": "Instrument Attributes",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "instrument",
        "descriptor_table": "attribute",
        "entity_join": "LEFT JOIN instrument i ON i.id = t.instrument_id",
        "entity_display": "i.display_name",
        "entity_alias": "instrument",
        "value_column": "t.attribute_value",
        "is_metadata": False,
        "has_period": False,
        "order": "t.timestamp DESC, i.display_name",
    },
    "instrument_period_attribute": {
        "label": "Instrument Period Attributes",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "instrument",
        "descriptor_table": "attribute",
        "entity_join": "LEFT JOIN instrument i ON i.id = t.instrument_id",
        "entity_display": "i.display_name",
        "entity_alias": "instrument",
        "value_column": "t.attribute_value",
        "is_metadata": False,
        "has_period": True,
        "period_column": "t.period_id",
        "period_join": "LEFT JOIN period pd ON pd.id = t.period_id",
        "period_display": "pd.display_name",
        "order": "t.timestamp DESC, i.display_name, pd.display_name",
    },
    "composite_attribute": {
        "label": "Composite Attributes",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "composite",
        "descriptor_table": "attribute",
        "entity_join": "LEFT JOIN composite c ON c.id = t.composite_id",
        "entity_display": "c.display_name",
        "entity_alias": "composite",
        "value_column": "t.attribute_value",
        "is_metadata": False,
        "has_period": False,
        "order": "t.timestamp DESC, c.display_name",
    },
    "composite_period_attribute": {
        "label": "Composite Period Attributes",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "composite",
        "descriptor_table": "attribute",
        "entity_join": "LEFT JOIN composite c ON c.id = t.composite_id",
        "entity_display": "c.display_name",
        "entity_alias": "composite",
        "value_column": "t.attribute_value",
        "is_metadata": False,
        "has_period": True,
        "period_column": "t.period_id",
        "period_join": "LEFT JOIN period pd ON pd.id = t.period_id",
        "period_display": "pd.display_name",
        "order": "t.timestamp DESC, c.display_name, pd.display_name",
    },
    "asset_metadata": {
        "label": "Asset Metadata",
        "entity_column": "t.asset_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "asset",
        "descriptor_table": "metadata",
        "entity_join": "LEFT JOIN asset a ON a.id = t.asset_id",
        "entity_display": "a.display_name",
        "entity_alias": "asset",
        "value_column": "t.value",
        "is_metadata": True,
        "has_period": False,
        "order": "t.timestamp DESC, a.display_name",
    },
    "instrument_metadata": {
        "label": "Instrument Metadata",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "instrument",
        "descriptor_table": "metadata",
        "entity_join": "LEFT JOIN instrument i ON i.id = t.instrument_id",
        "entity_display": "i.display_name",
        "entity_alias": "instrument",
        "value_column": "t.value",
        "is_metadata": True,
        "has_period": False,
        "order": "t.timestamp DESC, i.display_name",
    },
    "composite_metadata": {
        "label": "Composite Metadata",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "composite",
        "descriptor_table": "metadata",
        "entity_join": "LEFT JOIN composite c ON c.id = t.composite_id",
        "entity_display": "c.display_name",
        "entity_alias": "composite",
        "value_column": "t.value",
        "is_metadata": True,
        "has_period": False,
        "order": "t.timestamp DESC, c.display_name",
    },
    "provider_metadata": {
        "label": "Provider Metadata",
        "entity_column": "t.provider_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "provider",
        "descriptor_table": "metadata",
        "entity_join": "LEFT JOIN provider p ON p.id = t.provider_id",
        "entity_display": "p.display_name",
        "entity_alias": "provider",
        "value_column": "t.value",
        "is_metadata": True,
        "has_period": False,
        "order": "t.timestamp DESC, p.display_name",
    },
}

# Fixed column names that are always safe to sort on.
_FIXED_SORTABLE_COLUMNS = {
    "timestamp",
    "instrument",
    "composite",
    "asset",
    "provider",
    "period",
}

# Maximum number of descriptor columns in a single query.
_MAX_DESCRIPTOR_COLUMNS = 50


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_data_sources() -> list[DataSourceInfo]:
    """Return the list of available data sources."""
    sources: list[DataSourceInfo] = []
    for table, cfg in _DATA_EXPLORER_CONFIGS.items():
        entity_table = cfg["entity_table"]
        descriptor_table = cfg["descriptor_table"]
        sources.append(
            DataSourceInfo(
                table=table,
                label=cfg["label"],
                entity_type=entity_table,
                descriptor_type=descriptor_table,
                has_period=cfg.get("has_period", False),
            )
        )
    return sources


def get_filter_options(db: Session, table: str) -> DataExplorerFilterOptions:
    """Return entity/descriptor/period options for populating filter dropdowns."""
    cfg = _DATA_EXPLORER_CONFIGS.get(table)
    if cfg is None:
        raise BadRequestError(f"Unknown data source: {table}")

    entity_table = cfg["entity_table"]
    descriptor_table = cfg["descriptor_table"]

    entities = [
        FilterOption(id=row.id, display_name=row.display_name)
        for row in db.execute(
            text(
                f"SELECT id, display_name FROM {entity_table} WHERE is_active = true ORDER BY display_name"
            )
        )
    ]
    descriptors = [
        FilterOption(id=row.id, display_name=row.display_name)
        for row in db.execute(
            text(
                f"SELECT id, display_name FROM {descriptor_table} WHERE is_active = true ORDER BY display_name"
            )
        )
    ]

    periods = None
    if cfg.get("has_period"):
        periods = [
            FilterOption(id=row.id, display_name=row.display_name)
            for row in db.execute(
                text(
                    "SELECT id, display_name FROM period WHERE is_active = true ORDER BY display_name"
                )
            )
        ]

    return DataExplorerFilterOptions(entities=entities, descriptors=descriptors, periods=periods)


def query_data(
    db: Session,
    table: str,
    *,
    page: int = 1,
    page_size: int = 25,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    entity_ids: list[uuid.UUID] | None = None,
    descriptor_ids: list[uuid.UUID] | None = None,
    period_ids: list[uuid.UUID] | None = None,
    sort_field: str | None = None,
    sort_order: str = "desc",
) -> PaginatedResponse[dict]:
    """Execute a filtered, paginated query against a time-series table.

    Returns columnar output where each selected descriptor becomes a column.
    Each row represents a unique (timestamp, entity) group — or
    (timestamp, entity, period) for period-based tables.
    """
    cfg = _DATA_EXPLORER_CONFIGS.get(table)
    if cfg is None:
        raise BadRequestError(f"Unknown data source: {table}")

    # -- Step 1: Resolve descriptors (id → name) for column generation -----
    descriptors = _resolve_descriptors(db, cfg, descriptor_ids)
    descriptor_names = [d[1] for d in descriptors]
    descriptor_id_strs = [str(d[0]) for d in descriptors]

    # -- Step 2: Build WHERE clause ----------------------------------------
    where_parts: list[str] = []
    params: dict = {}

    if start is not None:
        where_parts.append("t.timestamp >= :start")
        params["start"] = start
    if end is not None:
        where_parts.append("t.timestamp < :end")
        params["end"] = end
    if entity_ids:
        where_parts.append(f"{cfg['entity_column']} IN :entity_ids")
        params["entity_ids"] = [str(eid) for eid in entity_ids]
    if descriptor_id_strs:
        where_parts.append(f"{cfg['descriptor_column']} IN :descriptor_ids")
        params["descriptor_ids"] = descriptor_id_strs
    if period_ids and cfg.get("period_column"):
        where_parts.append(f"{cfg['period_column']} IN :period_ids")
        params["period_ids"] = [str(pid) for pid in period_ids]

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # -- Step 3: Build GROUP BY dimensions ---------------------------------
    has_period = cfg.get("has_period", False)
    entity_col = cfg["entity_column"]

    group_cols = ["t.timestamp", entity_col, cfg["entity_display"]]
    if has_period:
        group_cols.extend([cfg["period_column"], cfg["period_display"]])
    group_by = ", ".join(group_cols)

    # -- Step 4: Build joins (entity + optional period, no descriptor) -----
    joins = cfg["entity_join"]
    if has_period:
        joins += " " + cfg["period_join"]

    # -- Step 5: COUNT query (on grouped rows) -----------------------------
    count_group_cols = ["t.timestamp", entity_col]
    if has_period:
        count_group_cols.append(cfg["period_column"])

    count_sql = (
        f"SELECT COUNT(*) FROM ("
        f"SELECT 1 FROM {table} t {where_clause} "
        f"GROUP BY {', '.join(count_group_cols)}"
        f") sub"
    )
    count_stmt = _bind_expanding_params(text(count_sql), params)
    total = db.execute(count_stmt, params).scalar() or 0

    # -- Step 6: Build SELECT with CASE WHEN columns -----------------------
    value_expr = cfg["value_column"]
    if cfg["is_metadata"]:
        value_expr = f"({cfg['value_column']} #>> '{{}}')"

    case_columns = []
    for i, (did, dname) in enumerate(descriptors):
        param_key = f"d{i}"
        case_columns.append(
            f"MAX(CASE WHEN {cfg['descriptor_column']} = :{param_key} "
            f'THEN {value_expr} END) AS "{dname}"'
        )
        params[param_key] = str(did)

    entity_alias = cfg["entity_alias"]
    select_parts = [
        "t.timestamp",
        f"{entity_col} AS {entity_alias}_id",
        f"{cfg['entity_display']} AS {entity_alias}",
    ]
    if has_period:
        select_parts.append(f"{cfg['period_column']} AS period_id")
        select_parts.append(f"{cfg['period_display']} AS period")
    select_parts.extend(case_columns)

    # -- Step 7: ORDER BY --------------------------------------------------
    sortable = _FIXED_SORTABLE_COLUMNS | set(descriptor_names)
    direction = "ASC" if sort_order.lower() == "asc" else "DESC"

    if sort_field and sort_field in sortable:
        # Descriptor names are all-caps identifiers — quote them for safety
        if sort_field in descriptor_names:
            order_clause = f'"{sort_field}" {direction}'
        else:
            order_clause = f"{sort_field} {direction}"
    else:
        order_clause = cfg["order"]

    # -- Step 8: Data query ------------------------------------------------
    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {table} t {joins}{where_clause} "
        f"GROUP BY {group_by} "
        f"ORDER BY {order_clause} "
        f"LIMIT :limit OFFSET :offset"
    )
    params["limit"] = page_size
    params["offset"] = offset

    data_stmt = _bind_expanding_params(text(data_sql), params)
    rows = [dict(row._mapping) for row in db.execute(data_stmt, params)]

    # Serialize datetime/UUID values
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                row[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                row[key] = str(value)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    # Build column list for the frontend
    columns = ["timestamp", entity_alias]
    if has_period:
        columns.append("period")
    columns.extend(descriptor_names)

    return PaginatedResponse[dict](
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        columns=columns,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_descriptors(
    db: Session,
    cfg: dict,
    descriptor_ids: list[uuid.UUID] | None,
) -> list[tuple[uuid.UUID, str]]:
    """Resolve descriptor IDs to (id, name) pairs.

    If no IDs provided, returns all active descriptors for the table (capped).
    Uses the ``name`` field (unique, all-caps Identifier) as the column name.
    """
    descriptor_table = cfg["descriptor_table"]

    if descriptor_ids:
        id_strs = [str(d) for d in descriptor_ids]
        stmt = text(
            f"SELECT id, name FROM {descriptor_table} WHERE id IN :ids ORDER BY name"
        ).bindparams(bindparam("ids", expanding=True))
        rows = db.execute(stmt, {"ids": id_strs}).fetchall()
    else:
        stmt = text(
            f"SELECT id, name FROM {descriptor_table} "
            f"WHERE is_active = true ORDER BY name LIMIT :lim"
        )
        rows = db.execute(stmt, {"lim": _MAX_DESCRIPTOR_COLUMNS}).fetchall()

    if not rows:
        return []

    if len(rows) > _MAX_DESCRIPTOR_COLUMNS:
        raise BadRequestError(
            f"Too many descriptor columns ({len(rows)}). Maximum is {_MAX_DESCRIPTOR_COLUMNS}."
        )

    return [(row.id, row.name) for row in rows]


def _bind_expanding_params(stmt, params: dict):
    """Bind expanding (IN-list) parameters to a text statement."""
    if "entity_ids" in params:
        stmt = stmt.bindparams(bindparam("entity_ids", expanding=True))
    if "descriptor_ids" in params:
        stmt = stmt.bindparams(bindparam("descriptor_ids", expanding=True))
    if "period_ids" in params:
        stmt = stmt.bindparams(bindparam("period_ids", expanding=True))
    return stmt
