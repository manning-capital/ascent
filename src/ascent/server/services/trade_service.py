import datetime
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ascent.database.models import (
    Order,
    OrderStatus,
    Trade,
    TradeCondition,
    TradeDataSeries,
    TradeLeg,
    TradeSnapshot,
    TradeStatus,
    TradeStatusType,
)
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.orders import OrderDetailSchema, OrderStatusSchema
from ascent.server.schemas.trades import (
    TradeConditionCreate,
    TradeConditionSchema,
    TradeCreate,
    TradeDataSeriesCreate,
    TradeDataSeriesSchema,
    TradeDetail,
    TradeLegCreate,
    TradeLegDetail,
    TradeLegSummary,
    TradeLegUpdate,
    TradeListItem,
    TradeSnapshotCreate,
    TradeSnapshotSchema,
    TradeStatusCreate,
    TradeStatusSchema,
    TradeUpdate,
)

TRADE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"OPENING", "CANCELLED"},
    "OPENING": {"OPEN", "CANCELLED", "ERROR"},
    "OPEN": {"CLOSING", "ERROR"},
    "CLOSING": {"CLOSED", "ERROR"},
    "CLOSED": set(),
    "CANCELLED": set(),
    "ERROR": {"PENDING", "CANCELLED"},
}


def _compute_tags(trade: Trade) -> list[str]:
    tags: list[str] = []
    directions = {leg.direction for leg in trade.legs}
    if len(directions) > 1:
        tags.append("COMPOUND")
    elif "LONG" in directions:
        tags.append("LONG")
    elif "SHORT" in directions:
        tags.append("SHORT")
    if trade.is_paper:
        tags.append("PAPER")
    return tags


def _compute_display_symbol(trade: Trade) -> str:
    symbols = []
    for leg in trade.legs:
        if leg.instrument and leg.instrument.display_name:
            symbols.append(leg.instrument.display_name)
    return " + ".join(symbols) if symbols else ""


def _build_trade_list_item(trade: Trade) -> TradeListItem:
    legs = []
    for leg in trade.legs:
        legs.append(
            TradeLegSummary(
                id=leg.id,
                instrument_id=leg.instrument_id,
                instrument_name=leg.instrument.display_name if leg.instrument else "",
                direction=leg.direction,
                quantity=leg.quantity,
                entry_price=leg.entry_price,
                exit_price=leg.exit_price,
                realized_pnl=leg.realized_pnl,
            )
        )
    return TradeListItem(
        id=trade.id,
        strategy_id=trade.strategy_id,
        strategy_name=trade.strategy.display_name,
        is_paper=trade.is_paper,
        entry_at=trade.entry_at,
        exit_at=trade.exit_at,
        current_status=(trade.current_status_type.name if trade.current_status_type else None),
        total_realized_pnl=trade.total_realized_pnl,
        total_unrealized_pnl=trade.total_unrealized_pnl,
        total_fees=trade.total_fees,
        legs=legs,
        tags=_compute_tags(trade),
        display_symbol=_compute_display_symbol(trade),
    )


TRADE_SORT_COLUMNS = {
    "entry_at": Trade.entry_at,
    "exit_at": Trade.exit_at,
    "total_realized_pnl": Trade.total_realized_pnl,
    "total_unrealized_pnl": Trade.total_unrealized_pnl,
    "total_fees": Trade.total_fees,
}


def get_trades(
    db: Session,
    status: str | None = None,
    strategy_id: uuid.UUID | None = None,
    search: str | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    tags: list[str] | None = None,
    sort_field: str = "entry_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[TradeListItem], int]:
    from ascent.database.models.instruments import Instrument

    query = select(Trade).options(
        joinedload(Trade.strategy),
        joinedload(Trade.current_status_type),
        selectinload(Trade.legs).joinedload(TradeLeg.instrument),
    )

    if status:
        query = query.join(Trade.current_status_type).where(TradeStatusType.name == status)
    if strategy_id:
        query = query.where(Trade.strategy_id == strategy_id)
    if start_date:
        query = query.where(Trade.entry_at >= start_date)
    if end_date:
        query = query.where(Trade.entry_at <= end_date)
    if search:
        query = query.where(
            Trade.legs.any(TradeLeg.instrument.has(Instrument.display_name.ilike(f"%{search}%")))
        )

    # Tag filters — applied at DB level before pagination
    # Tags: LONG = only LONG legs, SHORT = only SHORT legs,
    #        COMPOUND = both LONG and SHORT legs, PAPER = is_paper flag
    if tags:
        tag_set = set(tags)
        has_long = Trade.legs.any(TradeLeg.direction == "LONG")
        has_short = Trade.legs.any(TradeLeg.direction == "SHORT")
        tag_conditions = []
        if "PAPER" in tag_set:
            tag_conditions.append(Trade.is_paper.is_(True))
        if "LONG" in tag_set:
            tag_conditions.append(and_(has_long, ~has_short))
        if "SHORT" in tag_set:
            tag_conditions.append(and_(has_short, ~has_long))
        if "COMPOUND" in tag_set:
            tag_conditions.append(and_(has_long, has_short))
        if tag_conditions:
            query = query.where(or_(*tag_conditions))

    # Build count query from the same filters
    count_query = select(func.count()).select_from(Trade)
    if status:
        count_query = count_query.join(Trade.current_status_type).where(
            TradeStatusType.name == status
        )
    if strategy_id:
        count_query = count_query.where(Trade.strategy_id == strategy_id)
    if start_date:
        count_query = count_query.where(Trade.entry_at >= start_date)
    if end_date:
        count_query = count_query.where(Trade.entry_at <= end_date)
    if search:
        count_query = count_query.where(
            Trade.legs.any(TradeLeg.instrument.has(Instrument.display_name.ilike(f"%{search}%")))
        )
    if tags:
        has_long_count = Trade.legs.any(TradeLeg.direction == "LONG")
        has_short_count = Trade.legs.any(TradeLeg.direction == "SHORT")
        tag_conditions_count = []
        if "PAPER" in tag_set:
            tag_conditions_count.append(Trade.is_paper.is_(True))
        if "LONG" in tag_set:
            tag_conditions_count.append(and_(has_long_count, ~has_short_count))
        if "SHORT" in tag_set:
            tag_conditions_count.append(and_(has_short_count, ~has_long_count))
        if "COMPOUND" in tag_set:
            tag_conditions_count.append(and_(has_long_count, has_short_count))
        if tag_conditions_count:
            count_query = count_query.where(or_(*tag_conditions_count))

    total = db.execute(count_query).scalar() or 0

    sort_col = TRADE_SORT_COLUMNS.get(sort_field, Trade.entry_at)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    query = query.order_by(sort_expr)
    query = query.offset((page - 1) * page_size).limit(page_size)

    trades = db.execute(query).unique().scalars().all()
    items = [_build_trade_list_item(t) for t in trades]

    return items, total


def get_exchange_trades(
    db: Session,
    exchange_id: uuid.UUID,
    page: int = 1,
    page_size: int = 10,
    sort_field: str = "entry_at",
    sort_order: str = "desc",
) -> tuple[list[TradeListItem], int]:
    base_filter = Trade.legs.any(TradeLeg.exchange_id == exchange_id)

    count_query = select(func.count()).select_from(Trade).where(base_filter)
    total = db.execute(count_query).scalar() or 0

    query = (
        select(Trade)
        .where(base_filter)
        .options(
            joinedload(Trade.strategy),
            joinedload(Trade.current_status_type),
            selectinload(Trade.legs).joinedload(TradeLeg.instrument),
        )
    )

    sort_col = TRADE_SORT_COLUMNS.get(sort_field, Trade.entry_at)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    query = query.order_by(sort_expr).offset((page - 1) * page_size).limit(page_size)

    trades = db.execute(query).unique().scalars().all()
    return [_build_trade_list_item(t) for t in trades], total


def get_trade_detail(db: Session, trade_id: uuid.UUID) -> TradeDetail:
    query = (
        select(Trade)
        .where(Trade.id == trade_id)
        .options(
            joinedload(Trade.strategy),
            joinedload(Trade.current_status_type),
            selectinload(Trade.legs).joinedload(TradeLeg.instrument),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.order_type),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.exchange),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.instrument),
            selectinload(Trade.legs)
            .selectinload(TradeLeg.orders)
            .selectinload(Order.statuses)
            .joinedload(OrderStatus.order_status_type),
            selectinload(Trade.conditions).joinedload(TradeCondition.attribute),
            selectinload(Trade.data_series).joinedload(TradeDataSeries.attribute),
            selectinload(Trade.snapshots).joinedload(TradeSnapshot.attribute),
            selectinload(Trade.statuses).joinedload(TradeStatus.trade_status_type),
        )
    )
    trade = db.execute(query).unique().scalars().first()
    if not trade:
        raise NotFoundError("Trade not found")

    legs = []
    for leg in trade.legs:
        leg_orders = []
        for o in leg.orders:
            latest_status = o.statuses[-1] if o.statuses else None
            order_statuses = [
                OrderStatusSchema(
                    timestamp=s.timestamp,
                    status=s.order_status_type.name,
                    error_message=s.error_message,
                    error_code=s.error_code,
                )
                for s in o.statuses
            ]
            leg_orders.append(
                OrderDetailSchema(
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
                    current_status=(
                        latest_status.order_status_type.name if latest_status else None
                    ),
                    exchange_name=o.exchange.display_name if o.exchange else None,
                    statuses=order_statuses,
                )
            )
        legs.append(
            TradeLegDetail(
                id=leg.id,
                instrument_id=leg.instrument_id,
                instrument_name=leg.instrument.display_name if leg.instrument else "",
                direction=leg.direction,
                quantity=leg.quantity,
                entry_price=leg.entry_price,
                exit_price=leg.exit_price,
                realized_pnl=leg.realized_pnl,
                expected_entry_price=leg.expected_entry_price,
                expected_exit_price=leg.expected_exit_price,
                orders=leg_orders,
            )
        )

    conditions = [
        TradeConditionSchema(
            id=c.id,
            condition_type=c.condition_type,
            attribute_name=c.attribute.name,
            operator=c.operator,
            threshold_value=c.threshold_value,
            is_met=c.is_met,
            met_at=c.met_at,
        )
        for c in trade.conditions
    ]

    data_series = [
        TradeDataSeriesSchema(
            id=ds.id,
            attribute_name=ds.attribute.name,
            label=ds.label,
            data_source=ds.data_source,
        )
        for ds in trade.data_series
    ]

    snapshots = [
        TradeSnapshotSchema(
            attribute_name=s.attribute.name,
            snapshot_type=s.snapshot_type,
            attribute_value=s.attribute_value,
            timestamp=s.timestamp,
        )
        for s in trade.snapshots
    ]

    statuses = [
        TradeStatusSchema(
            timestamp=s.timestamp,
            status=s.trade_status_type.name,
        )
        for s in trade.statuses
    ]

    return TradeDetail(
        id=trade.id,
        strategy_id=trade.strategy_id,
        strategy_name=trade.strategy.display_name,
        is_paper=trade.is_paper,
        entry_at=trade.entry_at,
        exit_at=trade.exit_at,
        current_status=(trade.current_status_type.name if trade.current_status_type else None),
        total_realized_pnl=trade.total_realized_pnl,
        total_unrealized_pnl=trade.total_unrealized_pnl,
        total_fees=trade.total_fees,
        legs=legs,
        tags=_compute_tags(trade),
        display_symbol=_compute_display_symbol(trade),
        close_reason=trade.close_reason,
        parameters=trade.parameters,
        conditions=conditions,
        data_series=data_series,
        snapshots=snapshots,
        statuses=statuses,
    )


def create_trade(db: Session, data: TradeCreate) -> Trade:
    from ascent.server.services import exchange_resolution_service

    legs_data = data.legs
    trade = Trade(**data.model_dump(exclude={"legs"}))
    db.add(trade)
    db.flush()

    for leg_data in legs_data:
        leg_dict = leg_data.model_dump()
        # Auto-resolve exchange_id if not provided
        if leg_dict.get("exchange_id") is None:
            try:
                leg_dict["exchange_id"] = (
                    exchange_resolution_service.resolve_exchange_for_instrument(
                        db, data.strategy_id, leg_data.instrument_id
                    )
                )
            except Exception:
                # Resolution is best-effort; leave as None if no exchanges configured
                pass
        leg = TradeLeg(trade_id=trade.id, **leg_dict)
        db.add(leg)

    db.commit()
    db.refresh(trade)
    return trade


def update_trade(db: Session, trade_id: uuid.UUID, data: TradeUpdate) -> Trade:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(trade, key, value)
    db.commit()
    db.refresh(trade)
    return trade


def delete_trade(db: Session, trade_id: uuid.UUID) -> None:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    db.delete(trade)
    db.commit()


def add_trade_leg(db: Session, trade_id: uuid.UUID, data: TradeLegCreate) -> TradeLeg:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    leg = TradeLeg(trade_id=trade_id, **data.model_dump())
    db.add(leg)
    db.commit()
    db.refresh(leg)
    return leg


def update_trade_leg(db: Session, leg_id: uuid.UUID, data: TradeLegUpdate) -> TradeLeg:
    leg = db.get(TradeLeg, leg_id)
    if not leg:
        raise NotFoundError("Trade leg not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(leg, key, value)
    db.commit()
    db.refresh(leg)
    return leg


def delete_trade_leg(db: Session, leg_id: uuid.UUID) -> None:
    leg = db.get(TradeLeg, leg_id)
    if not leg:
        raise NotFoundError("Trade leg not found")
    db.delete(leg)
    db.commit()


def add_trade_status(db: Session, trade_id: uuid.UUID, data: TradeStatusCreate) -> TradeStatus:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")

    new_status_type = db.get(TradeStatusType, data.trade_status_type_id)
    if not new_status_type:
        raise NotFoundError("Trade status type not found")

    # Validate transition
    if trade.current_status_type_id is None:
        if new_status_type.name != "PENDING":
            raise BadRequestError(f"First trade status must be PENDING, got {new_status_type.name}")
    else:
        current_type = db.get(TradeStatusType, trade.current_status_type_id)
        current_symbol = current_type.name if current_type else None
        if current_symbol:
            allowed = TRADE_STATUS_TRANSITIONS.get(current_symbol, set())
            if new_status_type.name not in allowed:
                raise BadRequestError(
                    f"Invalid trade status transition: {current_symbol} -> {new_status_type.name}. "
                    f"Allowed transitions from {current_symbol}: {sorted(allowed)}"
                )

    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    status = TradeStatus(
        trade_id=trade_id,
        trade_status_type_id=data.trade_status_type_id,
        timestamp=ts,
    )
    db.add(status)
    trade.current_status_type_id = data.trade_status_type_id
    db.commit()
    db.refresh(status)
    return status


def add_trade_condition(
    db: Session, trade_id: uuid.UUID, data: TradeConditionCreate
) -> TradeCondition:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    obj = TradeCondition(trade_id=trade_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def add_trade_snapshot(
    db: Session, trade_id: uuid.UUID, data: TradeSnapshotCreate
) -> TradeSnapshot:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    obj = TradeSnapshot(trade_id=trade_id, **data.model_dump())
    db.add(obj)
    db.commit()
    return obj


def add_trade_data_series(
    db: Session, trade_id: uuid.UUID, data: TradeDataSeriesCreate
) -> TradeDataSeries:
    trade = db.get(Trade, trade_id)
    if not trade:
        raise NotFoundError("Trade not found")
    obj = TradeDataSeries(trade_id=trade_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
