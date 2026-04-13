from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.metadata import (
    EntityUsage,
    MetadataTypeCreate,
    MetadataTypeSchema,
    MetadataTypeUpdate,
)
from ascent.server.services import field_service

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("", response_model=PaginatedResponse[MetadataTypeSchema])
def list_metadata(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
):
    items, total = field_service.get_metadata_types(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[MetadataTypeSchema.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", status_code=201, response_model=MetadataTypeSchema)
def create_metadata(data: MetadataTypeCreate, db: Session = Depends(get_db)):
    return MetadataTypeSchema.model_validate(field_service.create_metadata_type(db, data))


@router.get("/{metadata_id}", response_model=MetadataTypeSchema)
def get_metadata(metadata_id: str, db: Session = Depends(get_db)):
    return MetadataTypeSchema.model_validate(field_service.get_metadata_type(db, metadata_id))


@router.put("/{metadata_id}", response_model=MetadataTypeSchema)
def update_metadata(metadata_id: str, data: MetadataTypeUpdate, db: Session = Depends(get_db)):
    return MetadataTypeSchema.model_validate(
        field_service.update_metadata_type(db, metadata_id, data)
    )


@router.get("/{metadata_id}/usage", response_model=EntityUsage)
def get_metadata_usage(metadata_id: str, db: Session = Depends(get_db)):
    return field_service.get_metadata_type_usage(db, metadata_id)


@router.delete("/{metadata_id}", status_code=204)
def delete_metadata(metadata_id: str, db: Session = Depends(get_db)):
    field_service.delete_metadata_type(db, metadata_id)
