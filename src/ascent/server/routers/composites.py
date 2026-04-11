import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.composites import (
    CompositeCreate,
    CompositeMemberCreate,
    CompositeSchema,
    CompositeUpdate,
)
from ascent.server.schemas.metadata import (
    BatchMetadataCreate,
    BulkHistoryUpdate,
    EntityUsage,
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataHistoryGrid,
)
from ascent.server.services import composite_service, field_service, metadata_service

router = APIRouter(tags=["composites"])


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------


@router.get("/composites/search", response_model=PaginatedResponse[CompositeSchema])
def search_composites(
    search: str | None = None,
    composite_type_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    exclude_strategy_id: uuid.UUID | None = None,
    exclude_feed_id: uuid.UUID | None = None,
    restrict_to_strategy_id: uuid.UUID | None = None,
    sort_field: str = "display_name",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    items, total = composite_service.search_composites(
        db,
        search=search,
        composite_type_id=composite_type_id,
        is_active=is_active,
        exclude_strategy_id=exclude_strategy_id,
        exclude_feed_id=exclude_feed_id,
        restrict_to_strategy_id=restrict_to_strategy_id,
        sort_field=sort_field,
        sort_order=sort_order,
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


@router.get("/composites/ids", response_model=list[uuid.UUID])
def search_composite_ids(
    search: str | None = None,
    composite_type_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    exclude_strategy_id: uuid.UUID | None = None,
    exclude_feed_id: uuid.UUID | None = None,
    restrict_to_strategy_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    return composite_service.search_composite_ids(
        db,
        search=search,
        composite_type_id=composite_type_id,
        is_active=is_active,
        exclude_strategy_id=exclude_strategy_id,
        exclude_feed_id=exclude_feed_id,
        restrict_to_strategy_id=restrict_to_strategy_id,
    )


@router.get("/composites", response_model=list[CompositeSchema])
def list_composites(db: Session = Depends(get_db)):
    return composite_service.get_composites(db)


@router.get("/composites/{composite_id}", response_model=CompositeSchema)
def get_composite(composite_id: uuid.UUID, db: Session = Depends(get_db)):
    return composite_service.get_composite(db, composite_id)


@router.get("/composites/{composite_id}/usage", response_model=EntityUsage)
def get_composite_usage(composite_id: uuid.UUID, db: Session = Depends(get_db)):
    return field_service.get_composite_usage(db, composite_id)


@router.post("/composites", status_code=201, response_model=CompositeSchema)
def create_composite(data: CompositeCreate, db: Session = Depends(get_db)):
    composite = composite_service.create_composite(db, data)
    return composite_service.get_composite(db, composite.id)


@router.put("/composites/{composite_id}")
def update_composite(composite_id: uuid.UUID, data: CompositeUpdate, db: Session = Depends(get_db)):
    return composite_service.update_composite(db, composite_id, data)


@router.delete("/composites/{composite_id}", status_code=204)
def delete_composite(composite_id: uuid.UUID, db: Session = Depends(get_db)):
    composite_service.delete_composite(db, composite_id)


# ---------------------------------------------------------------------------
# Composite Members
# ---------------------------------------------------------------------------


@router.post("/composites/{composite_id}/members", status_code=201)
def add_composite_member(
    composite_id: uuid.UUID, data: CompositeMemberCreate, db: Session = Depends(get_db)
):
    return composite_service.add_composite_member(db, composite_id, data)


@router.delete("/composites/{composite_id}/members/{instrument_id}", status_code=204)
def remove_composite_member(
    composite_id: uuid.UUID, instrument_id: uuid.UUID, db: Session = Depends(get_db)
):
    composite_service.remove_composite_member(db, composite_id, instrument_id)


# ---------------------------------------------------------------------------
# Composite Metadata
# ---------------------------------------------------------------------------


@router.get(
    "/composites/{composite_id}/metadata",
    response_model=list[MetadataEntrySchema],
)
def list_composite_metadata(composite_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_latest_composite_metadata(db, composite_id)


@router.post(
    "/composites/{composite_id}/metadata",
    status_code=201,
    response_model=MetadataEntrySchema,
)
def create_composite_metadata(
    composite_id: uuid.UUID,
    data: MetadataEntryCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.create_composite_metadata_entry(db, composite_id, data)


@router.post(
    "/composites/{composite_id}/metadata/batch",
    status_code=201,
    response_model=list[MetadataEntrySchema],
)
def batch_create_composite_metadata(
    composite_id: uuid.UUID,
    data: BatchMetadataCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.batch_create_composite_metadata(db, composite_id, data)


@router.get(
    "/composites/{composite_id}/metadata/history",
    response_model=MetadataHistoryGrid,
)
def get_composite_metadata_history(composite_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_composite_metadata_history_grid(db, composite_id)


@router.put(
    "/composites/{composite_id}/metadata/history/bulk",
    status_code=204,
)
def bulk_update_composite_metadata_history(
    composite_id: uuid.UUID,
    data: BulkHistoryUpdate,
    db: Session = Depends(get_db),
):
    metadata_service.bulk_update_composite_metadata_history(db, composite_id, data)
