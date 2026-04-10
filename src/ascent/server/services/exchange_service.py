import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Exchange
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.exchanges import (
    ExchangeCreate,
    ExchangeSchema,
    ExchangeUpdate,
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
