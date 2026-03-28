import uuid

from sqlalchemy import select
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
        exchange_type_name=e.exchange_type.name if e.exchange_type else None,
        name=e.name,
        description=e.description,
        provider_id=e.provider_id,
        provider_name=e.provider.name if e.provider else None,
        implementation_class=e.implementation_class,
        config=e.config,
        is_active=e.is_active,
        created_at=e.created_at,
    )


def get_exchanges(db: Session) -> list[ExchangeSchema]:
    query = (
        select(Exchange)
        .options(
            joinedload(Exchange.exchange_type),
            joinedload(Exchange.provider),
        )
        .order_by(Exchange.name)
    )
    exchanges = db.execute(query).unique().scalars().all()
    return [_build_exchange_schema(e) for e in exchanges]


def get_exchange(db: Session, exchange_id: uuid.UUID) -> ExchangeSchema:
    query = (
        select(Exchange)
        .options(
            joinedload(Exchange.exchange_type),
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
