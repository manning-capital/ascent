import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.exchanges import (
    ExchangeCreate,
    ExchangeSchema,
    ExchangeUpdate,
)
from ascent.server.services import exchange_service

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


@router.get("", response_model=PaginatedResponse[ExchangeSchema])
def list_exchanges(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
):
    items, total = exchange_service.get_exchanges(
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
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{exchange_id}", response_model=ExchangeSchema)
def get_exchange(exchange_id: uuid.UUID, db: Session = Depends(get_db)):
    return exchange_service.get_exchange(db, exchange_id)


@router.post("", status_code=201)
def create_exchange(data: ExchangeCreate, db: Session = Depends(get_db)):
    return exchange_service.create_exchange(db, data)


@router.put("/{exchange_id}")
def update_exchange(exchange_id: uuid.UUID, data: ExchangeUpdate, db: Session = Depends(get_db)):
    return exchange_service.update_exchange(db, exchange_id, data)


@router.delete("/{exchange_id}", status_code=204)
def delete_exchange(exchange_id: uuid.UUID, db: Session = Depends(get_db)):
    exchange_service.delete_exchange(db, exchange_id)
