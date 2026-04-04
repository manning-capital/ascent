"""Feed API router — CRUD for feeds and runs."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.engine.cache import EngineCache
from ascent.server.dependencies import get_cache, get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.feeds import (
    FeedCreate,
    FeedDependencyCreate,
    FeedDependencySchema,
    FeedDetail,
    FeedListItem,
    FeedPartitionItem,
    FeedPublishRequest,
    FeedPublishResponse,
    FeedRunListItem,
    FeedUpdate,
    StrategyFeedItem,
)
from ascent.server.schemas.universe import (
    CompositeUniverseBatchAdd,
    CompositeUniverseItemSchema,
    UniverseBatchAddInstruments,
    UniverseItemCreate,
    UniverseItemSchema,
)
from ascent.server.services import feed_service, universe_service

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("", response_model=list[FeedListItem])
def list_feeds(db: Session = Depends(get_db)):
    return feed_service.get_feeds(db)


@router.post("", status_code=201)
def create_feed(data: FeedCreate, db: Session = Depends(get_db)):
    return feed_service.create_feed(db, data)


@router.get("/{feed_id}", response_model=FeedDetail)
def get_feed(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    return feed_service.get_feed_detail(db, feed_id)


@router.put("/{feed_id}")
def update_feed(feed_id: uuid.UUID, data: FeedUpdate, db: Session = Depends(get_db)):
    return feed_service.update_feed(db, feed_id, data)


@router.delete("/{feed_id}", status_code=204)
def delete_feed(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    feed_service.delete_feed(db, feed_id)


@router.get("/{feed_id}/parameter-schema")
def get_feed_parameter_schema(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    feed = feed_service.get_feed_detail(db, feed_id)
    return feed.parameter_schema or {}


@router.get("/{feed_id}/runs/{run_id}", response_model=FeedRunListItem)
def get_feed_run(feed_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    return feed_service.get_feed_run(db, feed_id, run_id)


@router.get("/{feed_id}/runs", response_model=PaginatedResponse[FeedRunListItem])
def list_feed_runs(
    feed_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = feed_service.get_feed_runs(
        db,
        feed_id,
        page=page,
        page_size=page_size,
        started_after=started_after,
        started_before=started_before,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{feed_id}/partitions", response_model=PaginatedResponse[FeedPartitionItem])
def list_feed_partitions(
    feed_id: uuid.UUID,
    start: str | None = None,
    end: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    items, total = feed_service.list_partitions(
        db,
        feed_id,
        start=start,
        end=end,
        status=status,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{feed_id}/partitions/{partition_id}/data",
    response_model=PaginatedResponse[dict],
)
def get_partition_data(
    feed_id: uuid.UUID,
    partition_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    return feed_service.get_partition_data(
        db, feed_id, partition_id, page=page, page_size=page_size
    )


@router.post("/{feed_id}/publish", response_model=FeedPublishResponse, status_code=201)
def publish_feed_data(
    feed_id: uuid.UUID,
    body: FeedPublishRequest,
    db: Session = Depends(get_db),
    cache: EngineCache = Depends(get_cache),
):
    return feed_service.publish_feed_data(
        db, feed_id, body.records, cache, partition_key=body.partition_key
    )


@router.get("/{feed_id}/universe", response_model=list[UniverseItemSchema])
def get_feed_universe(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    return universe_service.get_feed_universe(db, feed_id)


@router.post("/{feed_id}/universe", status_code=201)
def add_feed_universe_item(
    feed_id: uuid.UUID, data: UniverseItemCreate, db: Session = Depends(get_db)
):
    return universe_service.add_feed_universe_item(db, feed_id, data)


@router.delete(
    "/{feed_id}/universe/{instrument_id}",
    status_code=204,
)
def remove_feed_universe_item(
    feed_id: uuid.UUID,
    instrument_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    universe_service.remove_feed_universe_item(db, feed_id, instrument_id)


@router.post("/{feed_id}/universe/batch", response_model=list[UniverseItemSchema])
def batch_add_feed_instruments(
    feed_id: uuid.UUID, data: UniverseBatchAddInstruments, db: Session = Depends(get_db)
):
    return universe_service.batch_add_feed_instruments(db, feed_id, data)


# ---- Composite Universe ----


@router.get("/{feed_id}/composite-universe", response_model=list[CompositeUniverseItemSchema])
def list_feed_composite_universe(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    return universe_service.get_feed_composite_universe(db, feed_id)


@router.post(
    "/{feed_id}/composite-universe/batch", response_model=list[CompositeUniverseItemSchema]
)
def batch_add_feed_composites(
    feed_id: uuid.UUID, data: CompositeUniverseBatchAdd, db: Session = Depends(get_db)
):
    return universe_service.batch_add_feed_composites(db, feed_id, data)


@router.delete("/{feed_id}/composite-universe/{composite_id}", status_code=204)
def remove_feed_composite_universe_item(
    feed_id: uuid.UUID, composite_id: uuid.UUID, db: Session = Depends(get_db)
):
    universe_service.remove_feed_composite_universe_item(db, feed_id, composite_id)


@router.get("/{feed_id}/dependencies", response_model=list[FeedDependencySchema])
def list_feed_dependencies(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    return feed_service.get_feed_dependencies(db, feed_id)


@router.post("/{feed_id}/dependencies", status_code=201, response_model=FeedDependencySchema)
def create_feed_dependency(
    feed_id: uuid.UUID, data: FeedDependencyCreate, db: Session = Depends(get_db)
):
    return feed_service.create_feed_dependency(db, feed_id, data)


@router.get("/{feed_id}/strategies", response_model=list[StrategyFeedItem])
def list_feed_strategies(feed_id: uuid.UUID, db: Session = Depends(get_db)):
    return feed_service.get_feed_strategy_feeds(db, feed_id)
