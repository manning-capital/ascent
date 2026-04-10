import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ascent.database.models import Order, OrderStatus, OrderStatusType
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.orders import OrderCreate, OrderSchema, OrderStatusCreate, OrderUpdate

ORDER_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "SUBMITTED": {"ACCEPTED", "REJECTED", "CANCELLED"},
    "ACCEPTED": {"PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"},
    "PARTIALLY_FILLED": {"PARTIALLY_FILLED", "FILLED", "CANCELLED"},
    "FILLED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
}


def _build_order_schemas(orders: list[Order]) -> list[OrderSchema]:
    items = []
    for o in orders:
        latest_status = o.statuses[-1] if o.statuses else None
        items.append(
            OrderSchema(
                id=o.id,
                timestamp=o.timestamp,
                order_type=o.order_type.display_name,
                side=o.side,
                instrument_id=o.instrument_id,
                instrument_name=o.instrument.display_name if o.instrument else "",
                quantity=o.quantity,
                price=o.price,
                filled_quantity=o.filled_quantity,
                average_fill_price=o.average_fill_price,
                external_order_id=o.external_order_id,
                time_in_force=o.time_in_force,
                current_status=(latest_status.order_status_type.name if latest_status else None),
                exchange_name=o.exchange.display_name if o.exchange else None,
            )
        )
    return items


def get_orders(db: Session) -> list[OrderSchema]:
    query = (
        select(Order)
        .options(
            joinedload(Order.order_type),
            joinedload(Order.exchange),
            joinedload(Order.instrument),
            selectinload(Order.statuses).joinedload(OrderStatus.order_status_type),
        )
        .order_by(Order.timestamp.desc())
    )
    orders = db.execute(query).unique().scalars().all()
    return _build_order_schemas(orders)


ORDER_SORT_COLUMNS = {
    "timestamp": Order.timestamp,
    "side": Order.side,
    "quantity": Order.quantity,
    "price": Order.price,
    "filled_quantity": Order.filled_quantity,
}


def get_strategy_orders(
    db: Session,
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 10,
    sort_field: str = "timestamp",
    sort_order: str = "desc",
) -> tuple[list[OrderSchema], int]:
    from ascent.database.models import Trade, TradeLeg

    base = (
        select(Order)
        .join(TradeLeg, Order.trade_leg_id == TradeLeg.id)
        .join(Trade, TradeLeg.trade_id == Trade.id)
        .where(Trade.strategy_id == strategy_id)
    )

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

    sort_col = ORDER_SORT_COLUMNS.get(sort_field, Order.timestamp)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    query = (
        base.options(
            joinedload(Order.order_type),
            joinedload(Order.exchange),
            joinedload(Order.instrument),
            selectinload(Order.statuses).joinedload(OrderStatus.order_status_type),
        )
        .order_by(sort_expr)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = db.execute(query).unique().scalars().all()
    return _build_order_schemas(orders), total


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

    new_status_type = db.get(OrderStatusType, data.order_status_type_id)
    if not new_status_type:
        raise NotFoundError("Order status type not found")

    # Validate transition
    if order.statuses:
        current_status = order.statuses[-1]
        current_symbol = (
            current_status.order_status_type.name if current_status.order_status_type else None
        )
        if not current_symbol:
            current_type = db.get(OrderStatusType, current_status.order_status_type_id)
            current_symbol = current_type.name if current_type else None
        if current_symbol:
            allowed = ORDER_STATUS_TRANSITIONS.get(current_symbol, set())
            if new_status_type.name not in allowed:
                raise BadRequestError(
                    f"Invalid order status transition: {current_symbol} -> {new_status_type.name}. "
                    f"Allowed transitions from {current_symbol}: {sorted(allowed)}"
                )

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
