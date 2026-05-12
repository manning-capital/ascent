"""Data Explorer router — generic querying of historical time-series data."""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.data_explorer import (
    DataExplorerFilterOptions,
    DataSeriesResponse,
    DataSourceInfo,
)
from ascent.server.services import data_explorer_service

router = APIRouter(prefix="/data", tags=["data-explorer"])


@router.get("/sources", response_model=list[DataSourceInfo])
def list_data_sources():
    """Return the list of available data sources."""
    return data_explorer_service.get_data_sources()


@router.get("/filters", response_model=DataExplorerFilterOptions)
def get_filter_options(
    table: str,
    db: Session = Depends(get_db),
):
    """Return entity/descriptor/period options for populating filter dropdowns."""
    return data_explorer_service.get_filter_options(db, table)


@router.get("/series", response_model=DataSeriesResponse)
def query_series(
    table: str,
    entity_id: uuid.UUID,
    descriptor_id: uuid.UUID,
    period_id: uuid.UUID | None = None,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    bucket: str = "none",
    aggregation: str = "none",
    db: Session = Depends(get_db),
):
    """Return a single time-series for one (entity, descriptor[, period]) tuple.

    Used by the chart cells in the Data Explorer workspace. Optionally bucketed
    via TimescaleDB ``time_bucket`` and aggregated (mean/sum/min/max/count).
    """
    return data_explorer_service.query_series(
        db,
        table,
        entity_id=entity_id,
        descriptor_id=descriptor_id,
        period_id=period_id,
        start=start,
        end=end,
        bucket=bucket,
        aggregation=aggregation,
    )


@router.get("/query", response_model=PaginatedResponse[dict])
def query_data(
    table: str,
    page: int = 1,
    page_size: int = 25,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    entity_ids: list[uuid.UUID] | None = Query(None),
    descriptor_ids: list[uuid.UUID] | None = Query(None),
    period_ids: list[uuid.UUID] | None = Query(None),
    sort_field: str | None = None,
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    """Execute a filtered, paginated query against a time-series table."""
    return data_explorer_service.query_data(
        db,
        table,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
        entity_ids=entity_ids,
        descriptor_ids=descriptor_ids,
        period_ids=period_ids,
        sort_field=sort_field,
        sort_order=sort_order,
    )
