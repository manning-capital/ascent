from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.attributes import AttributeCreate, AttributeSchema, AttributeUpdate
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.metadata import EntityUsage
from ascent.server.services import field_service

router = APIRouter(prefix="/attributes", tags=["attributes"])


@router.get("", response_model=PaginatedResponse[AttributeSchema])
def list_attributes(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
):
    items, total = field_service.get_attributes(
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
        items=[AttributeSchema.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", status_code=201, response_model=AttributeSchema)
def create_attribute(data: AttributeCreate, db: Session = Depends(get_db)):
    return AttributeSchema.model_validate(field_service.create_attribute(db, data))


@router.get("/{attribute_id}", response_model=AttributeSchema)
def get_attribute(attribute_id: str, db: Session = Depends(get_db)):
    return AttributeSchema.model_validate(field_service.get_attribute(db, attribute_id))


@router.put("/{attribute_id}", response_model=AttributeSchema)
def update_attribute(attribute_id: str, data: AttributeUpdate, db: Session = Depends(get_db)):
    return AttributeSchema.model_validate(field_service.update_attribute(db, attribute_id, data))


@router.get("/{attribute_id}/usage", response_model=EntityUsage)
def get_attribute_usage(attribute_id: str, db: Session = Depends(get_db)):
    return field_service.get_attribute_usage(db, attribute_id)


@router.delete("/{attribute_id}", status_code=204)
def delete_attribute(attribute_id: str, db: Session = Depends(get_db)):
    field_service.delete_attribute(db, attribute_id)
