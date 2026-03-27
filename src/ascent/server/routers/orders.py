import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.orders import OrderCreate, OrderSchema, OrderStatusCreate, OrderUpdate
from ascent.server.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderSchema])
def list_orders(db: Session = Depends(get_db)):
    return order_service.get_orders(db)


@router.post("", status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    return order_service.create_order(db, data)


@router.put("/{order_id}")
def update_order(order_id: uuid.UUID, data: OrderUpdate, db: Session = Depends(get_db)):
    return order_service.update_order(db, order_id, data)


@router.post("/{order_id}/statuses", status_code=201)
def add_order_status(order_id: uuid.UUID, data: OrderStatusCreate, db: Session = Depends(get_db)):
    return order_service.add_order_status(db, order_id, data)
