import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    ExchangeCompositeScope,
    ExchangeInstrumentScope,
    FeedCompositeScope,
    StrategyCompositeScope,
    StrategyExchange,
    StrategyInstrumentScope,
)
from ascent.database.models.composites import CompositeMember
from ascent.database.models.exchanges import Exchange
from ascent.database.models.feeds import FeedInstrumentScope
from ascent.database.models.instruments import Instrument
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.universe import (
    CompositeUniverseBatchAdd,
    CompositeUniverseItemSchema,
    UniverseBatchAddInstruments,
    UniverseItemCreate,
    UniverseItemSchema,
)

# ---------------------------------------------------------------------------
# Tradeability validation
# ---------------------------------------------------------------------------


def _get_strategy_tradeable_pairs(
    db: Session, strategy_id: uuid.UUID
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Return set of (provider_id, instrument_type_id) tuples tradeable by this strategy's exchanges."""
    rows = db.execute(
        select(Exchange.provider_id, Exchange.instrument_type_id)
        .join(StrategyExchange, StrategyExchange.exchange_id == Exchange.id)
        .where(StrategyExchange.strategy_id == strategy_id)
    ).all()
    return {(r[0], r[1]) for r in rows}


def _validate_instruments_tradeable(
    db: Session, strategy_id: uuid.UUID, instrument_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any instruments are not tradeable on the strategy's exchanges."""
    tradeable_pairs = _get_strategy_tradeable_pairs(db, strategy_id)
    if not tradeable_pairs:
        raise BadRequestError(
            "This strategy has no exchanges configured. Add exchanges before adding instruments to the universe."
        )

    instruments = db.execute(
        select(
            Instrument.id,
            Instrument.provider_id,
            Instrument.instrument_type_id,
            Instrument.display_name,
        ).where(Instrument.id.in_(instrument_ids))
    ).all()
    non_tradeable = [
        str(r.display_name or r.id)
        for r in instruments
        if (r.provider_id, r.instrument_type_id) not in tradeable_pairs
    ]
    if non_tradeable:
        raise BadRequestError(
            f"The following instruments are not tradeable on this strategy's exchanges: {', '.join(non_tradeable)}"
        )


def _validate_composites_tradeable(
    db: Session, strategy_id: uuid.UUID, composite_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any composite has members not tradeable on the strategy's exchanges."""
    tradeable_pairs = _get_strategy_tradeable_pairs(db, strategy_id)
    if not tradeable_pairs:
        raise BadRequestError(
            "This strategy has no exchanges configured. Add exchanges before adding composites to the universe."
        )

    from ascent.database.models.composites import Composite

    for composite_id in composite_ids:
        members = db.execute(
            select(Instrument.display_name, Instrument.provider_id, Instrument.instrument_type_id)
            .join(CompositeMember, CompositeMember.instrument_id == Instrument.id)
            .where(CompositeMember.composite_id == composite_id)
        ).all()

        if not members:
            raise BadRequestError(f"Composite {composite_id} has no members")

        non_tradeable = [
            str(m.display_name)
            for m in members
            if (m.provider_id, m.instrument_type_id) not in tradeable_pairs
        ]
        if non_tradeable:
            composite = db.get(Composite, composite_id)
            name = composite.display_name if composite else str(composite_id)
            raise BadRequestError(
                f"Composite '{name}' has members not tradeable on this strategy's exchanges: {', '.join(non_tradeable)}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_item(scope) -> UniverseItemSchema:
    inst = scope.instrument
    return UniverseItemSchema(
        instrument_id=scope.instrument_id,
        instrument_name=inst.name if inst else None,
        instrument_display_name=inst.display_name if inst else None,
        instrument_type_id=inst.instrument_type_id if inst else None,
        is_active=inst.is_active if inst else True,
        order=scope.order,
    )


# ---------------------------------------------------------------------------
# Strategy Universe
# ---------------------------------------------------------------------------


def get_strategy_universe(db: Session, strategy_id: uuid.UUID) -> list[UniverseItemSchema]:
    query = (
        select(StrategyInstrumentScope)
        .where(StrategyInstrumentScope.strategy_id == strategy_id)
        .options(joinedload(StrategyInstrumentScope.instrument))
        .order_by(StrategyInstrumentScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes]


def get_strategy_universe_paginated(
    db: Session,
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[UniverseItemSchema], int]:
    base = select(StrategyInstrumentScope).where(StrategyInstrumentScope.strategy_id == strategy_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(StrategyInstrumentScope.instrument))
        .order_by(StrategyInstrumentScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes], total


def add_strategy_universe_item(
    db: Session, strategy_id: uuid.UUID, data: UniverseItemCreate
) -> StrategyInstrumentScope:
    _validate_instruments_tradeable(db, strategy_id, [data.instrument_id])
    scope = StrategyInstrumentScope(
        strategy_id=strategy_id,
        instrument_id=data.instrument_id,
        order=data.order,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_strategy_universe_item(
    db: Session,
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    scope = db.get(StrategyInstrumentScope, (strategy_id, instrument_id))
    if not scope:
        raise NotFoundError("Universe item not found")
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Feed Universe
# ---------------------------------------------------------------------------


def get_feed_universe(db: Session, feed_id: uuid.UUID) -> list[UniverseItemSchema]:
    query = (
        select(FeedInstrumentScope)
        .where(FeedInstrumentScope.feed_id == feed_id)
        .options(joinedload(FeedInstrumentScope.instrument))
        .order_by(FeedInstrumentScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes]


def get_feed_universe_paginated(
    db: Session,
    feed_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[UniverseItemSchema], int]:
    base = select(FeedInstrumentScope).where(FeedInstrumentScope.feed_id == feed_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(FeedInstrumentScope.instrument))
        .order_by(FeedInstrumentScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes], total


def add_feed_universe_item(
    db: Session, feed_id: uuid.UUID, data: UniverseItemCreate
) -> FeedInstrumentScope:
    scope = FeedInstrumentScope(
        feed_id=feed_id,
        instrument_id=data.instrument_id,
        order=data.order,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_feed_universe_item(
    db: Session,
    feed_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    scope = db.get(FeedInstrumentScope, (feed_id, instrument_id))
    if not scope:
        raise NotFoundError("Universe item not found")
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Batch add instruments
# ---------------------------------------------------------------------------


def batch_add_feed_instruments(
    db: Session, feed_id: uuid.UUID, data: UniverseBatchAddInstruments
) -> list[UniverseItemSchema]:
    existing = {
        r[0]
        for r in db.execute(
            select(FeedInstrumentScope.instrument_id).where(FeedInstrumentScope.feed_id == feed_id)
        ).all()
    }
    order = data.start_order
    for instrument_id in data.instrument_ids:
        if instrument_id in existing:
            continue
        existing.add(instrument_id)
        db.add(FeedInstrumentScope(feed_id=feed_id, instrument_id=instrument_id, order=order))
        order += 1
    db.commit()
    return get_feed_universe(db, feed_id)


def batch_add_strategy_instruments(
    db: Session, strategy_id: uuid.UUID, data: UniverseBatchAddInstruments
) -> list[UniverseItemSchema]:
    _validate_instruments_tradeable(db, strategy_id, data.instrument_ids)
    existing = {
        r[0]
        for r in db.execute(
            select(StrategyInstrumentScope.instrument_id).where(
                StrategyInstrumentScope.strategy_id == strategy_id
            )
        ).all()
    }
    order = data.start_order
    for instrument_id in data.instrument_ids:
        if instrument_id in existing:
            continue
        existing.add(instrument_id)
        db.add(
            StrategyInstrumentScope(
                strategy_id=strategy_id, instrument_id=instrument_id, order=order
            )
        )
        order += 1
    db.commit()
    return get_strategy_universe(db, strategy_id)


# ---------------------------------------------------------------------------
# Composite Universe helpers
# ---------------------------------------------------------------------------


def _build_composite_item(scope) -> CompositeUniverseItemSchema:
    comp = scope.composite
    return CompositeUniverseItemSchema(
        composite_id=scope.composite_id,
        composite_name=comp.name if comp else None,
        composite_display_name=comp.display_name if comp else None,
        composite_type_id=comp.composite_type_id if comp else None,
        is_active=comp.is_active if comp else True,
        order=scope.order,
    )


# ---------------------------------------------------------------------------
# Feed Composite Universe
# ---------------------------------------------------------------------------


def get_feed_composite_universe(
    db: Session, feed_id: uuid.UUID
) -> list[CompositeUniverseItemSchema]:
    query = (
        select(FeedCompositeScope)
        .where(FeedCompositeScope.feed_id == feed_id)
        .options(joinedload(FeedCompositeScope.composite))
        .order_by(FeedCompositeScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes]


def get_feed_composite_universe_paginated(
    db: Session,
    feed_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[CompositeUniverseItemSchema], int]:
    base = select(FeedCompositeScope).where(FeedCompositeScope.feed_id == feed_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(FeedCompositeScope.composite))
        .order_by(FeedCompositeScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes], total


def batch_add_feed_composites(
    db: Session, feed_id: uuid.UUID, data: CompositeUniverseBatchAdd
) -> list[CompositeUniverseItemSchema]:
    existing = {
        r[0]
        for r in db.execute(
            select(FeedCompositeScope.composite_id).where(FeedCompositeScope.feed_id == feed_id)
        ).all()
    }
    order = data.start_order
    for composite_id in data.composite_ids:
        if composite_id in existing:
            continue
        existing.add(composite_id)
        db.add(FeedCompositeScope(feed_id=feed_id, composite_id=composite_id, order=order))
        order += 1
    db.commit()
    return get_feed_composite_universe(db, feed_id)


def remove_feed_composite_universe_item(
    db: Session, feed_id: uuid.UUID, composite_id: uuid.UUID
) -> None:
    scope = db.get(FeedCompositeScope, (feed_id, composite_id))
    if not scope:
        raise NotFoundError("Composite universe item not found")
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Strategy Composite Universe
# ---------------------------------------------------------------------------


def get_strategy_composite_universe(
    db: Session, strategy_id: uuid.UUID
) -> list[CompositeUniverseItemSchema]:
    query = (
        select(StrategyCompositeScope)
        .where(StrategyCompositeScope.strategy_id == strategy_id)
        .options(joinedload(StrategyCompositeScope.composite))
        .order_by(StrategyCompositeScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes]


def get_strategy_composite_universe_paginated(
    db: Session,
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[CompositeUniverseItemSchema], int]:
    base = select(StrategyCompositeScope).where(StrategyCompositeScope.strategy_id == strategy_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(StrategyCompositeScope.composite))
        .order_by(StrategyCompositeScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes], total


def batch_add_strategy_composites(
    db: Session, strategy_id: uuid.UUID, data: CompositeUniverseBatchAdd
) -> list[CompositeUniverseItemSchema]:
    _validate_composites_tradeable(db, strategy_id, data.composite_ids)
    existing = {
        r[0]
        for r in db.execute(
            select(StrategyCompositeScope.composite_id).where(
                StrategyCompositeScope.strategy_id == strategy_id
            )
        ).all()
    }
    order = data.start_order
    for composite_id in data.composite_ids:
        if composite_id in existing:
            continue
        existing.add(composite_id)
        db.add(
            StrategyCompositeScope(strategy_id=strategy_id, composite_id=composite_id, order=order)
        )
        order += 1
    db.commit()
    return get_strategy_composite_universe(db, strategy_id)


def remove_strategy_composite_universe_item(
    db: Session, strategy_id: uuid.UUID, composite_id: uuid.UUID
) -> None:
    scope = db.get(StrategyCompositeScope, (strategy_id, composite_id))
    if not scope:
        raise NotFoundError("Composite universe item not found")
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Exchange Universe
# ---------------------------------------------------------------------------


def get_exchange_universe(db: Session, exchange_id: uuid.UUID) -> list[UniverseItemSchema]:
    query = (
        select(ExchangeInstrumentScope)
        .where(ExchangeInstrumentScope.exchange_id == exchange_id)
        .options(joinedload(ExchangeInstrumentScope.instrument))
        .order_by(ExchangeInstrumentScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes]


def get_exchange_universe_paginated(
    db: Session,
    exchange_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[UniverseItemSchema], int]:
    base = select(ExchangeInstrumentScope).where(ExchangeInstrumentScope.exchange_id == exchange_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(ExchangeInstrumentScope.instrument))
        .order_by(ExchangeInstrumentScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_item(s) for s in scopes], total


def add_exchange_universe_item(
    db: Session, exchange_id: uuid.UUID, data: UniverseItemCreate
) -> ExchangeInstrumentScope:
    scope = ExchangeInstrumentScope(
        exchange_id=exchange_id,
        instrument_id=data.instrument_id,
        order=data.order,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_exchange_universe_item(
    db: Session,
    exchange_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    scope = db.get(ExchangeInstrumentScope, (exchange_id, instrument_id))
    if not scope:
        raise NotFoundError("Universe item not found")
    db.delete(scope)
    db.commit()


def batch_add_exchange_instruments(
    db: Session, exchange_id: uuid.UUID, data: UniverseBatchAddInstruments
) -> list[UniverseItemSchema]:
    existing = {
        r[0]
        for r in db.execute(
            select(ExchangeInstrumentScope.instrument_id).where(
                ExchangeInstrumentScope.exchange_id == exchange_id
            )
        ).all()
    }
    order = data.start_order
    for instrument_id in data.instrument_ids:
        if instrument_id in existing:
            continue
        existing.add(instrument_id)
        db.add(
            ExchangeInstrumentScope(
                exchange_id=exchange_id, instrument_id=instrument_id, order=order
            )
        )
        order += 1
    db.commit()
    return get_exchange_universe(db, exchange_id)


# ---------------------------------------------------------------------------
# Exchange Composite Universe
# ---------------------------------------------------------------------------


def get_exchange_composite_universe(
    db: Session, exchange_id: uuid.UUID
) -> list[CompositeUniverseItemSchema]:
    query = (
        select(ExchangeCompositeScope)
        .where(ExchangeCompositeScope.exchange_id == exchange_id)
        .options(joinedload(ExchangeCompositeScope.composite))
        .order_by(ExchangeCompositeScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes]


def get_exchange_composite_universe_paginated(
    db: Session,
    exchange_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    sort_field: str = "order",
    sort_order: str = "asc",
) -> tuple[list[CompositeUniverseItemSchema], int]:
    base = select(ExchangeCompositeScope).where(ExchangeCompositeScope.exchange_id == exchange_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    query = (
        base.options(joinedload(ExchangeCompositeScope.composite))
        .order_by(ExchangeCompositeScope.order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scopes = db.execute(query).unique().scalars().all()
    return [_build_composite_item(s) for s in scopes], total


def batch_add_exchange_composites(
    db: Session, exchange_id: uuid.UUID, data: CompositeUniverseBatchAdd
) -> list[CompositeUniverseItemSchema]:
    existing = {
        r[0]
        for r in db.execute(
            select(ExchangeCompositeScope.composite_id).where(
                ExchangeCompositeScope.exchange_id == exchange_id
            )
        ).all()
    }
    order = data.start_order
    for composite_id in data.composite_ids:
        if composite_id in existing:
            continue
        existing.add(composite_id)
        db.add(
            ExchangeCompositeScope(exchange_id=exchange_id, composite_id=composite_id, order=order)
        )
        order += 1
    db.commit()
    return get_exchange_composite_universe(db, exchange_id)


def remove_exchange_composite_universe_item(
    db: Session, exchange_id: uuid.UUID, composite_id: uuid.UUID
) -> None:
    scope = db.get(ExchangeCompositeScope, (exchange_id, composite_id))
    if not scope:
        raise NotFoundError("Composite universe item not found")
    db.delete(scope)
    db.commit()
