import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ascent.database.models import Exchange, Order, OrderStatus, OrderStatusType, TradeLeg
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.exchanges import (
    ExchangeCreate,
    ExchangeSchema,
    ExchangeStats,
    ExchangeUpdate,
    RecentOrderItem,
    RecentTradeLegItem,
)


def _build_exchange_schema(e: Exchange) -> ExchangeSchema:
    return ExchangeSchema(
        id=e.id,
        exchange_type_id=e.exchange_type_id,
        exchange_type_name=e.exchange_type.display_name if e.exchange_type else None,
        instrument_type_id=e.instrument_type_id,
        instrument_type_name=e.instrument_type.display_name if e.instrument_type else None,
        name=e.name,
        display_name=e.display_name,
        description=e.description,
        provider_id=e.provider_id,
        provider_name=e.provider.display_name if e.provider else None,
        implementation_class=e.implementation_class,
        config=e.config,
        is_active=e.is_active,
        created_at=e.created_at,
    )


EXCHANGE_SORT_COLUMNS = {
    "display_name": Exchange.display_name,
    "name": Exchange.name,
    "exchange_type_name": Exchange.exchange_type_id,
    "instrument_type_name": Exchange.instrument_type_id,
    "provider_name": Exchange.provider_id,
    "created_at": Exchange.created_at,
    "is_active": Exchange.is_active,
}


def get_exchanges(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "name",
    sort_order: str = "asc",
) -> tuple[list[ExchangeSchema], int]:
    conditions = []
    if search:
        conditions.append(
            Exchange.display_name.ilike(f"%{search}%") | Exchange.name.ilike(f"%{search}%")
        )
    if is_active is not None:
        conditions.append(Exchange.is_active == is_active)

    count_q = select(func.count()).select_from(Exchange)
    if conditions:
        count_q = count_q.where(*conditions)
    total = db.execute(count_q).scalar() or 0

    query = select(Exchange).options(
        joinedload(Exchange.exchange_type),
        joinedload(Exchange.instrument_type),
        joinedload(Exchange.provider),
    )
    if conditions:
        query = query.where(*conditions)

    sort_col = EXCHANGE_SORT_COLUMNS.get(sort_field, Exchange.name)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    query = query.order_by(sort_expr).offset((page - 1) * page_size).limit(page_size)
    exchanges = db.execute(query).unique().scalars().all()
    return [_build_exchange_schema(e) for e in exchanges], total


def get_exchange(db: Session, exchange_id: uuid.UUID) -> ExchangeSchema:
    query = (
        select(Exchange)
        .options(
            joinedload(Exchange.exchange_type),
            joinedload(Exchange.instrument_type),
            joinedload(Exchange.provider),
        )
        .where(Exchange.id == exchange_id)
    )
    e = db.execute(query).unique().scalar_one_or_none()
    if not e:
        raise NotFoundError("Exchange not found")
    return _build_exchange_schema(e)


def create_exchange(db: Session, data: ExchangeCreate) -> Exchange:
    exchange = Exchange(**data.model_dump())
    db.add(exchange)
    db.commit()
    db.refresh(exchange)
    return exchange


def update_exchange(db: Session, exchange_id: uuid.UUID, data: ExchangeUpdate) -> Exchange:
    exchange = db.get(Exchange, exchange_id)
    if not exchange:
        raise NotFoundError("Exchange not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(exchange, key, value)
    db.commit()
    db.refresh(exchange)
    return exchange


def delete_exchange(db: Session, exchange_id: uuid.UUID) -> None:
    exchange = db.get(Exchange, exchange_id)
    if not exchange:
        raise NotFoundError("Exchange not found")
    db.delete(exchange)
    db.commit()


def get_exchange_stats(db: Session, exchange_id: uuid.UUID) -> ExchangeStats:
    # Total orders
    total_orders = (
        db.execute(select(func.count()).select_from(Order).where(Order.exchange_id == exchange_id))
        .scalar()
        or 0
    )

    # Orders by status: get latest status for each order, group by status name
    latest_status_subq = (
        select(
            OrderStatus.order_id,
            func.max(OrderStatus.timestamp).label("max_ts"),
        )
        .group_by(OrderStatus.order_id)
        .subquery()
    )
    status_counts_query = (
        select(OrderStatusType.name, func.count())
        .select_from(OrderStatus)
        .join(
            latest_status_subq,
            (OrderStatus.order_id == latest_status_subq.c.order_id)
            & (OrderStatus.timestamp == latest_status_subq.c.max_ts),
        )
        .join(Order, Order.id == OrderStatus.order_id)
        .join(OrderStatusType, OrderStatus.order_status_type_id == OrderStatusType.id)
        .where(Order.exchange_id == exchange_id)
        .group_by(OrderStatusType.name)
    )
    orders_by_status = dict(db.execute(status_counts_query).all())

    # Trade leg aggregates
    leg_agg = db.execute(
        select(
            func.count(),
            func.sum(TradeLeg.realized_pnl),
            func.sum(TradeLeg.quantity),
        )
        .select_from(TradeLeg)
        .where(TradeLeg.exchange_id == exchange_id)
    ).one()
    total_trade_legs = leg_agg[0] or 0
    total_realized_pnl = float(leg_agg[1]) if leg_agg[1] is not None else None
    total_volume = float(leg_agg[2]) if leg_agg[2] is not None else None

    # Recent orders (5 most recent)
    recent_orders_query = (
        select(Order)
        .where(Order.exchange_id == exchange_id)
        .options(
            joinedload(Order.instrument),
            selectinload(Order.statuses).joinedload(OrderStatus.order_status_type),
        )
        .order_by(Order.timestamp.desc())
        .limit(5)
    )
    recent_orders_raw = db.execute(recent_orders_query).unique().scalars().all()
    recent_orders = [
        RecentOrderItem(
            id=o.id,
            timestamp=o.timestamp,
            side=o.side,
            instrument_name=o.instrument.display_name if o.instrument else None,
            quantity=o.quantity,
            price=o.price,
            filled_quantity=o.filled_quantity,
            average_fill_price=o.average_fill_price,
            status=o.statuses[-1].order_status_type.name if o.statuses else None,
        )
        for o in recent_orders_raw
    ]

    # Recent trade legs (5 most recent)
    recent_legs_query = (
        select(TradeLeg)
        .where(TradeLeg.exchange_id == exchange_id)
        .options(joinedload(TradeLeg.instrument))
        .order_by(TradeLeg.created_at.desc())
        .limit(5)
    )
    recent_legs_raw = db.execute(recent_legs_query).unique().scalars().all()
    recent_trade_legs = [
        RecentTradeLegItem(
            id=leg.id,
            trade_id=leg.trade_id,
            instrument_name=leg.instrument.display_name if leg.instrument else None,
            direction=leg.direction,
            quantity=leg.quantity,
            entry_price=leg.entry_price,
            exit_price=leg.exit_price,
            realized_pnl=leg.realized_pnl,
            created_at=leg.created_at,
        )
        for leg in recent_legs_raw
    ]

    return ExchangeStats(
        total_orders=total_orders,
        orders_by_status=orders_by_status,
        total_trade_legs=total_trade_legs,
        total_realized_pnl=total_realized_pnl,
        total_volume=total_volume,
        recent_orders=recent_orders,
        recent_trade_legs=recent_trade_legs,
    )
