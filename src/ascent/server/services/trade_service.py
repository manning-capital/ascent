import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ascent.database.models import (
    Asset,
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
        from_sym = leg.from_asset.symbol or leg.from_asset.name
        to_sym = leg.to_asset.symbol or leg.to_asset.name
        symbols.append(f"{from_sym}/{to_sym}")
    return " + ".join(symbols)


def _build_trade_list_item(trade: Trade) -> TradeListItem:
    legs = []
    for leg in trade.legs:
        legs.append(
            TradeLegSummary(
                id=leg.id,
                from_asset_symbol=leg.from_asset.symbol or leg.from_asset.name,
                to_asset_symbol=leg.to_asset.symbol or leg.to_asset.name,
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
        strategy_name=trade.strategy.name,
        is_paper=trade.is_paper,
        entry_at=trade.entry_at,
        exit_at=trade.exit_at,
        current_status=(trade.current_status_type.symbol if trade.current_status_type else None),
        total_realized_pnl=trade.total_realized_pnl,
        total_unrealized_pnl=trade.total_unrealized_pnl,
        total_fees=trade.total_fees,
        legs=legs,
        tags=_compute_tags(trade),
        display_symbol=_compute_display_symbol(trade),
    )


def get_trades(
    db: Session,
    status: str | None = None,
    strategy_id: uuid.UUID | None = None,
    search: str | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    tags: list[str] | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[TradeListItem], int]:
    query = select(Trade).options(
        joinedload(Trade.strategy),
        joinedload(Trade.current_status_type),
        selectinload(Trade.legs).joinedload(TradeLeg.from_asset),
        selectinload(Trade.legs).joinedload(TradeLeg.to_asset),
    )

    if status:
        query = query.join(Trade.current_status_type).where(TradeStatusType.symbol == status)
    if strategy_id:
        query = query.where(Trade.strategy_id == strategy_id)
    if start_date:
        query = query.where(Trade.entry_at >= start_date)
    if end_date:
        query = query.where(Trade.entry_at <= end_date)
    if search:
        query = query.where(
            Trade.legs.any(
                TradeLeg.from_asset.has(Asset.symbol.ilike(f"%{search}%"))
                | TradeLeg.to_asset.has(Asset.symbol.ilike(f"%{search}%"))
                | TradeLeg.from_asset.has(Asset.name.ilike(f"%{search}%"))
                | TradeLeg.to_asset.has(Asset.name.ilike(f"%{search}%"))
            )
        )

    # Count total
    count_query = select(func.count()).select_from(Trade)
    if status:
        count_query = count_query.join(Trade.current_status_type).where(
            TradeStatusType.symbol == status
        )
    if strategy_id:
        count_query = count_query.where(Trade.strategy_id == strategy_id)
    if start_date:
        count_query = count_query.where(Trade.entry_at >= start_date)
    if end_date:
        count_query = count_query.where(Trade.entry_at <= end_date)
    if search:
        count_query = count_query.where(
            Trade.legs.any(
                TradeLeg.from_asset.has(Asset.symbol.ilike(f"%{search}%"))
                | TradeLeg.to_asset.has(Asset.symbol.ilike(f"%{search}%"))
                | TradeLeg.from_asset.has(Asset.name.ilike(f"%{search}%"))
                | TradeLeg.to_asset.has(Asset.name.ilike(f"%{search}%"))
            )
        )

    total = db.execute(count_query).scalar() or 0

    query = query.order_by(Trade.entry_at.desc().nullslast())
    query = query.offset((page - 1) * page_size).limit(page_size)

    trades = db.execute(query).unique().scalars().all()
    items = [_build_trade_list_item(t) for t in trades]

    # Filter by tags in-memory (compound logic requires loaded legs)
    if tags:
        tag_set = set(tags)
        items = [item for item in items if tag_set.intersection(item.tags)]

    return items, total


def get_trade_detail(db: Session, trade_id: uuid.UUID) -> TradeDetail:
    query = (
        select(Trade)
        .where(Trade.id == trade_id)
        .options(
            joinedload(Trade.strategy),
            joinedload(Trade.current_status_type),
            selectinload(Trade.legs).joinedload(TradeLeg.from_asset),
            selectinload(Trade.legs).joinedload(TradeLeg.to_asset),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.order_type),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.exchange),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.from_asset),
            selectinload(Trade.legs).selectinload(TradeLeg.orders).joinedload(Order.to_asset),
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
                    status=s.order_status_type.symbol,
                    error_message=s.error_message,
                    error_code=s.error_code,
                )
                for s in o.statuses
            ]
            leg_orders.append(
                OrderDetailSchema(
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
                    current_status=(
                        latest_status.order_status_type.symbol if latest_status else None
                    ),
                    exchange_name=o.exchange.name if o.exchange else None,
                    statuses=order_statuses,
                )
            )
        legs.append(
            TradeLegDetail(
                id=leg.id,
                from_asset_symbol=leg.from_asset.symbol or leg.from_asset.name,
                to_asset_symbol=leg.to_asset.symbol or leg.to_asset.name,
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
            status=s.trade_status_type.symbol,
        )
        for s in trade.statuses
    ]

    return TradeDetail(
        id=trade.id,
        strategy_id=trade.strategy_id,
        strategy_name=trade.strategy.name,
        is_paper=trade.is_paper,
        entry_at=trade.entry_at,
        exit_at=trade.exit_at,
        current_status=(trade.current_status_type.symbol if trade.current_status_type else None),
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
    legs_data = data.legs
    trade = Trade(**data.model_dump(exclude={"legs"}))
    db.add(trade)
    db.flush()

    for leg_data in legs_data:
        leg = TradeLeg(trade_id=trade.id, **leg_data.model_dump())
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
        if new_status_type.symbol != "PENDING":
            raise BadRequestError(
                f"First trade status must be PENDING, got {new_status_type.symbol}"
            )
    else:
        current_type = db.get(TradeStatusType, trade.current_status_type_id)
        current_symbol = current_type.symbol if current_type else None
        if current_symbol:
            allowed = TRADE_STATUS_TRANSITIONS.get(current_symbol, set())
            if new_status_type.symbol not in allowed:
                raise BadRequestError(
                    f"Invalid trade status transition: {current_symbol} -> {new_status_type.symbol}. "
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
