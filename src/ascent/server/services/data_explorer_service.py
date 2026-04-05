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
        "select": "t.instrument_id, i.display_name AS instrument, t.attribute_id, a.display_name AS attribute, t.attribute_value",
        "joins": (
            "LEFT JOIN instrument i ON i.id = t.instrument_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "t.timestamp DESC, i.display_name",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "instrument",
        "descriptor_table": "attribute",
        "has_period": False,
    },
    "instrument_period_attribute": {
        "label": "Instrument Period Attributes",
        "select": "t.instrument_id, i.display_name AS instrument, pd.display_name AS period, t.period_id, t.attribute_id, a.display_name AS attribute, t.attribute_value",
        "joins": (
            "LEFT JOIN instrument i ON i.id = t.instrument_id "
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "t.timestamp DESC, i.display_name, pd.display_name",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "instrument",
        "descriptor_table": "attribute",
        "has_period": True,
        "period_column": "t.period_id",
    },
    "composite_attribute": {
        "label": "Composite Attributes",
        "select": "t.composite_id, c.display_name AS composite, t.attribute_id, a.display_name AS attribute, t.attribute_value",
        "joins": (
            "LEFT JOIN composite c ON c.id = t.composite_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "t.timestamp DESC, c.display_name",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "composite",
        "descriptor_table": "attribute",
        "has_period": False,
    },
    "composite_period_attribute": {
        "label": "Composite Period Attributes",
        "select": "t.composite_id, c.display_name AS composite, pd.display_name AS period, t.period_id, t.attribute_id, a.display_name AS attribute, t.attribute_value",
        "joins": (
            "LEFT JOIN composite c ON c.id = t.composite_id "
            "LEFT JOIN period pd ON pd.id = t.period_id "
            "LEFT JOIN attribute a ON a.id = t.attribute_id"
        ),
        "order": "t.timestamp DESC, c.display_name, pd.display_name",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.attribute_id",
        "entity_table": "composite",
        "descriptor_table": "attribute",
        "has_period": True,
        "period_column": "t.period_id",
    },
    "asset_metadata": {
        "label": "Asset Metadata",
        "select": "t.asset_id, a.display_name AS asset, t.metadata_id, m.display_name AS metadata, t.value",
        "joins": (
            "LEFT JOIN asset a ON a.id = t.asset_id LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "t.timestamp DESC, a.display_name",
        "entity_column": "t.asset_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "asset",
        "descriptor_table": "metadata",
        "has_period": False,
    },
    "instrument_metadata": {
        "label": "Instrument Metadata",
        "select": "t.instrument_id, i.display_name AS instrument, t.metadata_id, m.display_name AS metadata, t.value",
        "joins": (
            "LEFT JOIN instrument i ON i.id = t.instrument_id "
            "LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "t.timestamp DESC, i.display_name",
        "entity_column": "t.instrument_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "instrument",
        "descriptor_table": "metadata",
        "has_period": False,
    },
    "composite_metadata": {
        "label": "Composite Metadata",
        "select": "t.composite_id, c.display_name AS composite, t.metadata_id, m.display_name AS metadata, t.value",
        "joins": (
            "LEFT JOIN composite c ON c.id = t.composite_id "
            "LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "t.timestamp DESC, c.display_name",
        "entity_column": "t.composite_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "composite",
        "descriptor_table": "metadata",
        "has_period": False,
    },
    "provider_metadata": {
        "label": "Provider Metadata",
        "select": "t.provider_id, p.display_name AS provider, t.metadata_id, m.display_name AS metadata, t.value",
        "joins": (
            "LEFT JOIN provider p ON p.id = t.provider_id "
            "LEFT JOIN metadata m ON m.id = t.metadata_id"
        ),
        "order": "t.timestamp DESC, p.display_name",
        "entity_column": "t.provider_id",
        "descriptor_column": "t.metadata_id",
        "entity_table": "provider",
        "descriptor_table": "metadata",
        "has_period": False,
    },
}

# Column names that are safe to sort on (prevents SQL injection via sort_field).
_SORTABLE_COLUMNS = {
    "timestamp",
    "instrument",
    "composite",
    "asset",
    "provider",
    "attribute",
    "metadata",
    "period",
    "attribute_value",
    "value",
}


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
    """Execute a filtered, paginated query against a time-series table."""
    cfg = _DATA_EXPLORER_CONFIGS.get(table)
    if cfg is None:
        raise BadRequestError(f"Unknown data source: {table}")

    # Build WHERE clause
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
    if descriptor_ids:
        where_parts.append(f"{cfg['descriptor_column']} IN :descriptor_ids")
        params["descriptor_ids"] = [str(did) for did in descriptor_ids]
    if period_ids and cfg.get("period_column"):
        where_parts.append(f"{cfg['period_column']} IN :period_ids")
        params["period_ids"] = [str(pid) for pid in period_ids]

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # Count query
    count_sql = f"SELECT COUNT(*) FROM {table} t {cfg['joins']}{where_clause}"
    count_stmt = text(count_sql)
    if "entity_ids" in params:
        count_stmt = count_stmt.bindparams(bindparam("entity_ids", expanding=True))
    if "descriptor_ids" in params:
        count_stmt = count_stmt.bindparams(bindparam("descriptor_ids", expanding=True))
    if "period_ids" in params:
        count_stmt = count_stmt.bindparams(bindparam("period_ids", expanding=True))
    total = db.execute(count_stmt, params).scalar() or 0

    # Order
    order_clause = cfg["order"]
    if sort_field and sort_field in _SORTABLE_COLUMNS:
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"
        order_clause = f"{sort_field} {direction}"

    # Data query
    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT t.timestamp, {cfg['select']} "
        f"FROM {table} t {cfg['joins']}{where_clause} "
        f"ORDER BY {order_clause} "
        f"LIMIT :limit OFFSET :offset"
    )
    params["limit"] = page_size
    params["offset"] = offset

    data_stmt = text(data_sql)
    if "entity_ids" in params:
        data_stmt = data_stmt.bindparams(bindparam("entity_ids", expanding=True))
    if "descriptor_ids" in params:
        data_stmt = data_stmt.bindparams(bindparam("descriptor_ids", expanding=True))
    if "period_ids" in params:
        data_stmt = data_stmt.bindparams(bindparam("period_ids", expanding=True))

    rows = [dict(row._mapping) for row in db.execute(data_stmt, params)]

    # Serialize datetime/UUID values
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
