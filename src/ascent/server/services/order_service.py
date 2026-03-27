import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ascent.database.models import Order, OrderStatus
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.orders import OrderCreate, OrderSchema, OrderStatusCreate, OrderUpdate


def get_orders(db: Session) -> list[OrderSchema]:
    query = (
        select(Order)
        .options(
            joinedload(Order.order_type),
            joinedload(Order.from_asset),
            joinedload(Order.to_asset),
            selectinload(Order.statuses).joinedload(OrderStatus.order_status_type),
        )
        .order_by(Order.timestamp.desc())
    )
    orders = db.execute(query).unique().scalars().all()

    items = []
    for o in orders:
        latest_status = o.statuses[-1] if o.statuses else None
        items.append(
            OrderSchema(
                id=o.id,
                timestamp=o.timestamp,
                order_type=o.order_type.name,
                side=o.side,
                from_asset_symbol=o.from_asset.symbol or o.from_asset.name,
                to_asset_symbol=o.to_asset.symbol or o.to_asset.name,
                quantity=o.quantity,
                price=o.price,
                filled_quantity=o.filled_quantity,
                average_fill_price=o.average_fill_price,
                external_order_id=o.external_order_id,
                time_in_force=o.time_in_force,
                current_status=(latest_status.order_status_type.symbol if latest_status else None),
            )
        )
    return items


def create_order(db: Session, data: OrderCreate) -> Order:
    order = Order(**data.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, order_id: uuid.UUID, data: OrderUpdate) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    db.commit()
    db.refresh(order)
    return order


def add_order_status(db: Session, order_id: uuid.UUID, data: OrderStatusCreate) -> OrderStatus:
    order = db.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    status = OrderStatus(
        order_id=order_id,
        order_status_type_id=data.order_status_type_id,
        timestamp=ts,
        error_message=data.error_message,
        error_code=data.error_code,
    )
    db.add(status)
    db.commit()
    db.refresh(status)
    return status
