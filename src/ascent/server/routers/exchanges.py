import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.exchanges import (
    ExchangeCreate,
    ExchangeSchema,
    ExchangeUpdate,
)
from ascent.server.services import exchange_service

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


@router.get("", response_model=list[ExchangeSchema])
def list_exchanges(db: Session = Depends(get_db)):
    return exchange_service.get_exchanges(db)


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
