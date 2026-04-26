import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    FeedCompositeScope,
    StrategyCompositeScope,
    StrategyExchange,
    StrategyInstrumentScope,
)
from ascent.database.models.composites import Composite, CompositeMember
from ascent.database.models.exchanges import Exchange
from ascent.database.models.feeds import Feed, FeedInstrumentScope, StrategyFeed
from ascent.database.models.instruments import Instrument
from ascent.database.models.strategy import Strategy as StrategyModel
from ascent.database.models.trades import Trade as TradeRow
from ascent.database.models.trades import TradeLeg as TradeLegRow
from ascent.database.models.types import TradeStatusType
from ascent.server.exceptions import BadRequestError, ConflictError, NotFoundError
from ascent.server.schemas.universe import (
    BlockingScopeItem,
    BlockingTrade,
    CompositeUniverseBatchAdd,
    CompositeUniverseItemSchema,
    ImpactReport,
    UniverseBatchAddInstruments,
    UniverseItemCreate,
    UniverseItemSchema,
)

_TERMINAL_TRADE_STATES: tuple[str, ...] = ("CLOSED", "CANCELLED", "REJECTED")


# ---------------------------------------------------------------------------
# Bitemporal helpers — single chokepoint for scope-table reads/writes.
# Every read uses `dropped_at IS NULL`; every insert sets `added_at=now()`;
# every "remove" or "deactivate" soft-drops by setting `dropped_at=now()`.
# ---------------------------------------------------------------------------


def _active_scope(
    db: Session,
    model: Any,
    parent_col: str,
    parent_id: uuid.UUID,
    member_col: str,
    member_id: uuid.UUID,
) -> Any:
    """Return the currently-active row for `(parent_id, member_id)` or None."""
    return db.execute(
        select(model)
        .where(getattr(model, parent_col) == parent_id)
        .where(getattr(model, member_col) == member_id)
        .where(model.dropped_at.is_(None))
    ).scalar_one_or_none()


def _add_scope(
    db: Session,
    model: Any,
    *,
    parent_col: str,
    parent_id: uuid.UUID,
    member_col: str,
    member_id: uuid.UUID,
    order: int,
) -> Any:
    """Idempotent insert of an active scope row."""
    existing = db.execute(
        select(model)
        .where(getattr(model, parent_col) == parent_id)
        .where(getattr(model, member_col) == member_id)
        .where(model.dropped_at.is_(None))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = model(
        **{parent_col: parent_id, member_col: member_id},
        order=order,
        added_at=datetime.now(UTC),
    )
    db.add(row)
    return row


def _drop_scope(
    db: Session,
    model: Any,
    *,
    parent_col: str,
    parent_id: uuid.UUID,
    member_col: str,
    member_id: uuid.UUID,
) -> Any | None:
    """Soft-drop the active row if any. Returns the row (now dropped) or None."""
    row = db.execute(
        select(model)
        .where(getattr(model, parent_col) == parent_id)
        .where(getattr(model, member_col) == member_id)
        .where(model.dropped_at.is_(None))
    ).scalar_one_or_none()
    if row is not None:
        row.dropped_at = datetime.now(UTC)
    return row


# ---------------------------------------------------------------------------
# Strategy-side validation
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


def _get_strategy_feed_instrument_ids(db: Session, strategy_id: uuid.UUID) -> set[uuid.UUID]:
    """Union of active FeedInstrumentScope.instrument_id across this strategy's feeds."""
    rows = db.execute(
        select(FeedInstrumentScope.instrument_id)
        .join(StrategyFeed, StrategyFeed.feed_id == FeedInstrumentScope.feed_id)
        .where(StrategyFeed.strategy_id == strategy_id)
        .where(FeedInstrumentScope.dropped_at.is_(None))
    ).all()
    return {r[0] for r in rows}


def _get_strategy_feed_composite_ids(db: Session, strategy_id: uuid.UUID) -> set[uuid.UUID]:
    """Union of active FeedCompositeScope.composite_id across this strategy's feeds."""
    rows = db.execute(
        select(FeedCompositeScope.composite_id)
        .join(StrategyFeed, StrategyFeed.feed_id == FeedCompositeScope.feed_id)
        .where(StrategyFeed.strategy_id == strategy_id)
        .where(FeedCompositeScope.dropped_at.is_(None))
    ).all()
    return {r[0] for r in rows}


def _validate_instruments_tradeable(
    db: Session, strategy_id: uuid.UUID, instrument_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any instrument is unreachable for this strategy.

    A strategy universe instrument is valid iff:
    1. Its (provider_id, instrument_type_id) matches one of the strategy's exchanges, AND
    2. It appears in at least one of the strategy's feeds' active instrument scope.
    """
    tradeable_pairs = _get_strategy_tradeable_pairs(db, strategy_id)
    if not tradeable_pairs:
        raise BadRequestError(
            "This strategy has no exchanges configured. Add exchanges before adding instruments to the universe."
        )

    fed_ids = _get_strategy_feed_instrument_ids(db, strategy_id)
    if not fed_ids:
        raise BadRequestError(
            "This strategy has no feeds covering any instruments. Add an instrument to a linked feed's scope before adding it to the strategy universe."
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

    not_fed = [str(r.display_name or r.id) for r in instruments if r.id not in fed_ids]
    if not_fed:
        raise BadRequestError(
            f"The following instruments have no price data from this strategy's feeds: {', '.join(not_fed)}"
        )


def _validate_composites_tradeable(
    db: Session, strategy_id: uuid.UUID, composite_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any composite is unreachable for this strategy.

    A strategy universe composite is valid iff:
    1. All its members' (provider_id, instrument_type_id) match one of the strategy's exchanges, AND
    2. The composite appears in at least one of the strategy's feeds' active composite scope.
    """
    tradeable_pairs = _get_strategy_tradeable_pairs(db, strategy_id)
    if not tradeable_pairs:
        raise BadRequestError(
            "This strategy has no exchanges configured. Add exchanges before adding composites to the universe."
        )

    fed_composite_ids = _get_strategy_feed_composite_ids(db, strategy_id)

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

        if composite_id not in fed_composite_ids:
            composite = db.get(Composite, composite_id)
            name = composite.display_name if composite else str(composite_id)
            raise BadRequestError(
                f"Composite '{name}' is not in any of this strategy's composite-scoped feeds. "
                "Add it to a linked feed's composite scope first."
            )


# ---------------------------------------------------------------------------
# Feed-side validation
# ---------------------------------------------------------------------------


def _validate_feed_instrument_compatibility(
    db: Session, feed_id: uuid.UUID, instrument_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any instrument doesn't match the feed's declared type.

    Composite-scoped feeds (composite_type_id set, instrument_type_id NULL) can never
    accept instruments — those go in FeedCompositeScope.
    """
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError(f"Feed {feed_id} not found")

    if feed.instrument_type_id is None:
        raise BadRequestError(
            f"Feed '{feed.display_name or feed.name}' is composite-scoped and cannot accept instruments. "
            "Add composites via the composite-universe endpoint instead."
        )

    rows = db.execute(
        select(
            Instrument.id,
            Instrument.provider_id,
            Instrument.instrument_type_id,
            Instrument.display_name,
        ).where(Instrument.id.in_(instrument_ids))
    ).all()

    mismatches = [
        str(r.display_name or r.id)
        for r in rows
        if (r.provider_id, r.instrument_type_id) != (feed.provider_id, feed.instrument_type_id)
    ]
    if mismatches:
        raise BadRequestError(
            f"The following instruments don't match this feed's provider and instrument type: {', '.join(mismatches)}"
        )


def _validate_feed_composite_compatibility(
    db: Session, feed_id: uuid.UUID, composite_ids: list[uuid.UUID]
) -> None:
    """Raise BadRequestError if any composite doesn't match the feed's declared composite type.

    Instrument-scoped feeds (instrument_type_id set, composite_type_id NULL) can never
    accept composites — those go in FeedInstrumentScope.
    """
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError(f"Feed {feed_id} not found")

    if feed.composite_type_id is None:
        raise BadRequestError(
            f"Feed '{feed.display_name or feed.name}' is instrument-scoped and cannot accept composites. "
            "Add instruments via the universe endpoint instead."
        )

    rows = db.execute(
        select(Composite.id, Composite.composite_type_id, Composite.display_name).where(
            Composite.id.in_(composite_ids)
        )
    ).all()

    mismatches = [
        str(r.display_name or r.id) for r in rows if r.composite_type_id != feed.composite_type_id
    ]
    if mismatches:
        raise BadRequestError(
            f"The following composites don't match this feed's composite type: {', '.join(mismatches)}"
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
        is_active=(scope.dropped_at is None),
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
    scope = _add_scope(
        db,
        StrategyInstrumentScope,
        parent_col="strategy_id",
        parent_id=strategy_id,
        member_col="instrument_id",
        member_id=data.instrument_id,
        order=data.order,
    )
    db.commit()
    db.refresh(scope)
    return scope


def remove_strategy_universe_item(
    db: Session,
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    scope = _active_scope(
        db,
        StrategyInstrumentScope,
        "strategy_id",
        strategy_id,
        "instrument_id",
        instrument_id,
    )
    if not scope:
        raise NotFoundError("Universe item not found")
    impact = compute_strategy_universe_impact(db, strategy_id, instrument_id)
    if not impact.can_remove:
        raise ConflictError(_format_impact_message(impact))
    scope.dropped_at = datetime.now(UTC)
    db.commit()


def set_strategy_universe_item_active(
    db: Session,
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
    is_active: bool,
) -> StrategyInstrumentScope:
    if is_active:
        scope = _add_scope(
            db,
            StrategyInstrumentScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="instrument_id",
            member_id=instrument_id,
            order=0,
        )
    else:
        scope = _drop_scope(
            db,
            StrategyInstrumentScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="instrument_id",
            member_id=instrument_id,
        )
        if scope is None:
            raise NotFoundError("Universe item not found")
    db.commit()
    db.refresh(scope)
    return scope


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
    _validate_feed_instrument_compatibility(db, feed_id, [data.instrument_id])
    scope = _add_scope(
        db,
        FeedInstrumentScope,
        parent_col="feed_id",
        parent_id=feed_id,
        member_col="instrument_id",
        member_id=data.instrument_id,
        order=data.order,
    )
    db.commit()
    db.refresh(scope)
    return scope


def remove_feed_universe_item(
    db: Session,
    feed_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    scope = _active_scope(
        db, FeedInstrumentScope, "feed_id", feed_id, "instrument_id", instrument_id
    )
    if not scope:
        raise NotFoundError("Universe item not found")
    impact = compute_feed_universe_impact(db, feed_id, instrument_id)
    if not impact.can_remove:
        raise ConflictError(_format_impact_message(impact))
    scope.dropped_at = datetime.now(UTC)
    db.commit()


def set_feed_universe_item_active(
    db: Session,
    feed_id: uuid.UUID,
    instrument_id: uuid.UUID,
    is_active: bool,
) -> FeedInstrumentScope:
    if is_active:
        scope = _add_scope(
            db,
            FeedInstrumentScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="instrument_id",
            member_id=instrument_id,
            order=0,
        )
    else:
        # Disabling feed-scope items is gated on open trades that need price data.
        blocking_trades = _trades_blocking_feed_disable(db, feed_id, instrument_id)
        if blocking_trades:
            impact = ImpactReport(
                can_remove=False,
                reasons=[
                    f"{len(blocking_trades)} open trade(s) need price data from this feed",
                ],
                blocking_trades=blocking_trades,
                suggested_action="clear_blockers",
            )
            raise ConflictError(_format_impact_message(impact))
        scope = _drop_scope(
            db,
            FeedInstrumentScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="instrument_id",
            member_id=instrument_id,
        )
        if scope is None:
            raise NotFoundError("Universe item not found")
    db.commit()
    db.refresh(scope)
    return scope


# ---------------------------------------------------------------------------
# Batch add instruments
# ---------------------------------------------------------------------------


def batch_add_feed_instruments(
    db: Session, feed_id: uuid.UUID, data: UniverseBatchAddInstruments
) -> list[UniverseItemSchema]:
    _validate_feed_instrument_compatibility(db, feed_id, data.instrument_ids)
    existing = {
        r[0]
        for r in db.execute(
            select(FeedInstrumentScope.instrument_id)
            .where(FeedInstrumentScope.feed_id == feed_id)
            .where(FeedInstrumentScope.dropped_at.is_(None))
        ).all()
    }
    order = data.start_order
    for instrument_id in data.instrument_ids:
        if instrument_id in existing:
            continue
        existing.add(instrument_id)
        _add_scope(
            db,
            FeedInstrumentScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="instrument_id",
            member_id=instrument_id,
            order=order,
        )
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
            select(StrategyInstrumentScope.instrument_id)
            .where(StrategyInstrumentScope.strategy_id == strategy_id)
            .where(StrategyInstrumentScope.dropped_at.is_(None))
        ).all()
    }
    order = data.start_order
    for instrument_id in data.instrument_ids:
        if instrument_id in existing:
            continue
        existing.add(instrument_id)
        _add_scope(
            db,
            StrategyInstrumentScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="instrument_id",
            member_id=instrument_id,
            order=order,
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
        is_active=(scope.dropped_at is None),
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
    _validate_feed_composite_compatibility(db, feed_id, data.composite_ids)
    existing = {
        r[0]
        for r in db.execute(
            select(FeedCompositeScope.composite_id)
            .where(FeedCompositeScope.feed_id == feed_id)
            .where(FeedCompositeScope.dropped_at.is_(None))
        ).all()
    }
    order = data.start_order
    for composite_id in data.composite_ids:
        if composite_id in existing:
            continue
        existing.add(composite_id)
        _add_scope(
            db,
            FeedCompositeScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="composite_id",
            member_id=composite_id,
            order=order,
        )
        order += 1
    db.commit()
    return get_feed_composite_universe(db, feed_id)


def remove_feed_composite_universe_item(
    db: Session, feed_id: uuid.UUID, composite_id: uuid.UUID
) -> None:
    scope = _active_scope(db, FeedCompositeScope, "feed_id", feed_id, "composite_id", composite_id)
    if not scope:
        raise NotFoundError("Composite universe item not found")
    impact = compute_feed_composite_universe_impact(db, feed_id, composite_id)
    if not impact.can_remove:
        raise ConflictError(_format_impact_message(impact))
    scope.dropped_at = datetime.now(UTC)
    db.commit()


def set_feed_composite_universe_item_active(
    db: Session, feed_id: uuid.UUID, composite_id: uuid.UUID, is_active: bool
) -> FeedCompositeScope:
    if is_active:
        scope = _add_scope(
            db,
            FeedCompositeScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="composite_id",
            member_id=composite_id,
            order=0,
        )
    else:
        blocking_trades = _trades_blocking_feed_composite_disable(db, feed_id, composite_id)
        if blocking_trades:
            impact = ImpactReport(
                can_remove=False,
                reasons=[
                    f"{len(blocking_trades)} open composite trade(s) need data from this feed",
                ],
                blocking_trades=blocking_trades,
                suggested_action="clear_blockers",
            )
            raise ConflictError(_format_impact_message(impact))
        scope = _drop_scope(
            db,
            FeedCompositeScope,
            parent_col="feed_id",
            parent_id=feed_id,
            member_col="composite_id",
            member_id=composite_id,
        )
        if scope is None:
            raise NotFoundError("Composite universe item not found")
    db.commit()
    db.refresh(scope)
    return scope


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
            select(StrategyCompositeScope.composite_id)
            .where(StrategyCompositeScope.strategy_id == strategy_id)
            .where(StrategyCompositeScope.dropped_at.is_(None))
        ).all()
    }
    order = data.start_order
    for composite_id in data.composite_ids:
        if composite_id in existing:
            continue
        existing.add(composite_id)
        _add_scope(
            db,
            StrategyCompositeScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="composite_id",
            member_id=composite_id,
            order=order,
        )
        order += 1
    db.commit()
    return get_strategy_composite_universe(db, strategy_id)


def remove_strategy_composite_universe_item(
    db: Session, strategy_id: uuid.UUID, composite_id: uuid.UUID
) -> None:
    scope = _active_scope(
        db, StrategyCompositeScope, "strategy_id", strategy_id, "composite_id", composite_id
    )
    if not scope:
        raise NotFoundError("Composite universe item not found")
    impact = compute_strategy_composite_impact(db, strategy_id, composite_id)
    if not impact.can_remove:
        raise ConflictError(_format_impact_message(impact))
    scope.dropped_at = datetime.now(UTC)
    db.commit()


def set_strategy_composite_universe_item_active(
    db: Session, strategy_id: uuid.UUID, composite_id: uuid.UUID, is_active: bool
) -> StrategyCompositeScope:
    if is_active:
        scope = _add_scope(
            db,
            StrategyCompositeScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="composite_id",
            member_id=composite_id,
            order=0,
        )
    else:
        scope = _drop_scope(
            db,
            StrategyCompositeScope,
            parent_col="strategy_id",
            parent_id=strategy_id,
            member_col="composite_id",
            member_id=composite_id,
        )
        if scope is None:
            raise NotFoundError("Composite universe item not found")
    db.commit()
    db.refresh(scope)
    return scope


# ---------------------------------------------------------------------------
# Impact computation
# ---------------------------------------------------------------------------


def _format_impact_message(impact: ImpactReport) -> str:
    if impact.reasons:
        return "; ".join(impact.reasons)
    return "Cannot remove: dependent records exist."


def _non_terminal_trades_for_strategy_instrument(
    db: Session, strategy_id: uuid.UUID, instrument_id: uuid.UUID
) -> list[BlockingTrade]:
    rows = db.execute(
        select(
            TradeRow.id,
            TradeRow.entry_at,
            TradeStatusType.name,
            TradeLegRow.direction,
            TradeLegRow.quantity,
        )
        .join(TradeLegRow, TradeLegRow.trade_id == TradeRow.id)
        .join(TradeStatusType, TradeStatusType.id == TradeRow.current_status_type_id)
        .where(TradeRow.strategy_id == strategy_id)
        .where(TradeLegRow.instrument_id == instrument_id)
        .where(TradeStatusType.name.notin_(_TERMINAL_TRADE_STATES))
    ).all()
    return [
        BlockingTrade(
            trade_id=trade_id,
            state=state,
            instrument_id=instrument_id,
            direction=direction,
            quantity=quantity,
            entry_at=entry_at.isoformat() if entry_at else None,
        )
        for trade_id, entry_at, state, direction, quantity in rows
    ]


def _non_terminal_trades_for_strategy_composite(
    db: Session, strategy_id: uuid.UUID, composite_id: uuid.UUID
) -> list[BlockingTrade]:
    """A composite trade is one whose leg-instrument-set exactly matches
    the composite's member-set. Mirrors :func:`_build_trade_columns`.
    """
    member_ids = set(
        db.execute(
            select(CompositeMember.instrument_id).where(
                CompositeMember.composite_id == composite_id
            )
        ).scalars()
    )
    if not member_ids:
        return []

    candidate_rows = db.execute(
        select(TradeRow.id, TradeRow.entry_at, TradeStatusType.name)
        .join(TradeStatusType, TradeStatusType.id == TradeRow.current_status_type_id)
        .where(TradeRow.strategy_id == strategy_id)
        .where(TradeStatusType.name.notin_(_TERMINAL_TRADE_STATES))
    ).all()

    result: list[BlockingTrade] = []
    for trade_id, entry_at, state in candidate_rows:
        leg_ids = set(
            db.execute(
                select(TradeLegRow.instrument_id).where(TradeLegRow.trade_id == trade_id)
            ).scalars()
        )
        if leg_ids == member_ids:
            result.append(
                BlockingTrade(
                    trade_id=trade_id,
                    state=state,
                    composite_id=composite_id,
                    entry_at=entry_at.isoformat() if entry_at else None,
                )
            )
    return result


def _non_terminal_trades_for_exchange_assignment(
    db: Session, strategy_id: uuid.UUID, exchange_id: uuid.UUID
) -> list[BlockingTrade]:
    rows = db.execute(
        select(
            TradeRow.id,
            TradeRow.entry_at,
            TradeStatusType.name,
            TradeLegRow.instrument_id,
            TradeLegRow.direction,
            TradeLegRow.quantity,
        )
        .join(TradeLegRow, TradeLegRow.trade_id == TradeRow.id)
        .join(TradeStatusType, TradeStatusType.id == TradeRow.current_status_type_id)
        .where(TradeRow.strategy_id == strategy_id)
        .where(TradeLegRow.exchange_id == exchange_id)
        .where(TradeStatusType.name.notin_(_TERMINAL_TRADE_STATES))
    ).all()
    return [
        BlockingTrade(
            trade_id=trade_id,
            state=state,
            instrument_id=inst_id,
            direction=direction,
            quantity=quantity,
            entry_at=entry_at.isoformat() if entry_at else None,
        )
        for trade_id, entry_at, state, inst_id, direction, quantity in rows
    ]


def _trades_blocking_feed_disable(
    db: Session, feed_id: uuid.UUID, instrument_id: uuid.UUID
) -> list[BlockingTrade]:
    """Open trades on this instrument from any strategy that uses this feed."""
    rows = db.execute(
        select(
            TradeRow.id,
            TradeRow.entry_at,
            TradeRow.strategy_id,
            TradeStatusType.name,
            TradeLegRow.direction,
            TradeLegRow.quantity,
        )
        .join(TradeLegRow, TradeLegRow.trade_id == TradeRow.id)
        .join(TradeStatusType, TradeStatusType.id == TradeRow.current_status_type_id)
        .join(StrategyFeed, StrategyFeed.strategy_id == TradeRow.strategy_id)
        .where(StrategyFeed.feed_id == feed_id)
        .where(TradeLegRow.instrument_id == instrument_id)
        .where(TradeStatusType.name.notin_(_TERMINAL_TRADE_STATES))
    ).all()
    return [
        BlockingTrade(
            trade_id=trade_id,
            state=state,
            instrument_id=instrument_id,
            direction=direction,
            quantity=quantity,
            entry_at=entry_at.isoformat() if entry_at else None,
        )
        for trade_id, entry_at, _strategy_id, state, direction, quantity in rows
    ]


def _trades_blocking_feed_composite_disable(
    db: Session, feed_id: uuid.UUID, composite_id: uuid.UUID
) -> list[BlockingTrade]:
    """Open composite trades from any strategy that uses this feed."""
    member_ids = set(
        db.execute(
            select(CompositeMember.instrument_id).where(
                CompositeMember.composite_id == composite_id
            )
        ).scalars()
    )
    if not member_ids:
        return []

    strategy_ids = set(
        db.execute(
            select(StrategyFeed.strategy_id).where(StrategyFeed.feed_id == feed_id)
        ).scalars()
    )
    if not strategy_ids:
        return []

    candidate_rows = db.execute(
        select(TradeRow.id, TradeRow.entry_at, TradeStatusType.name)
        .join(TradeStatusType, TradeStatusType.id == TradeRow.current_status_type_id)
        .where(TradeRow.strategy_id.in_(strategy_ids))
        .where(TradeStatusType.name.notin_(_TERMINAL_TRADE_STATES))
    ).all()

    result: list[BlockingTrade] = []
    for trade_id, entry_at, state in candidate_rows:
        leg_ids = set(
            db.execute(
                select(TradeLegRow.instrument_id).where(TradeLegRow.trade_id == trade_id)
            ).scalars()
        )
        if leg_ids == member_ids:
            result.append(
                BlockingTrade(
                    trade_id=trade_id,
                    state=state,
                    composite_id=composite_id,
                    entry_at=entry_at.isoformat() if entry_at else None,
                )
            )
    return result


def _orphaned_universe_items_if_remove_exchange(
    db: Session, strategy_id: uuid.UUID, exchange_id: uuid.UUID
) -> list[BlockingScopeItem]:
    """Active strategy universe items that would be unreachable if this
    exchange were removed (no other strategy exchange covers their type).
    """
    exchange = db.get(Exchange, exchange_id)
    if exchange is None:
        return []

    other_pairs = set(
        db.execute(
            select(Exchange.provider_id, Exchange.instrument_type_id)
            .join(StrategyExchange, StrategyExchange.exchange_id == Exchange.id)
            .where(StrategyExchange.strategy_id == strategy_id)
            .where(StrategyExchange.exchange_id != exchange_id)
            .where(StrategyExchange.is_active.is_(True))
        ).all()
    )
    if (exchange.provider_id, exchange.instrument_type_id) in other_pairs:
        return []

    rows = db.execute(
        select(StrategyInstrumentScope.instrument_id, Instrument.display_name)
        .join(Instrument, Instrument.id == StrategyInstrumentScope.instrument_id)
        .where(StrategyInstrumentScope.strategy_id == strategy_id)
        .where(StrategyInstrumentScope.dropped_at.is_(None))
        .where(Instrument.provider_id == exchange.provider_id)
        .where(Instrument.instrument_type_id == exchange.instrument_type_id)
    ).all()

    return [
        BlockingScopeItem(
            scope_type="strategy_universe",
            strategy_id=strategy_id,
            instrument_id=inst_id,
            display_name=name,
        )
        for inst_id, name in rows
    ]


def compute_strategy_universe_impact(
    db: Session, strategy_id: uuid.UUID, instrument_id: uuid.UUID
) -> ImpactReport:
    blockers = _non_terminal_trades_for_strategy_instrument(db, strategy_id, instrument_id)
    if not blockers:
        return ImpactReport(can_remove=True)
    return ImpactReport(
        can_remove=False,
        reasons=[f"{len(blockers)} open trade(s) reference this instrument"],
        blocking_trades=blockers,
        suggested_action="disable",
    )


def compute_strategy_composite_impact(
    db: Session, strategy_id: uuid.UUID, composite_id: uuid.UUID
) -> ImpactReport:
    blockers = _non_terminal_trades_for_strategy_composite(db, strategy_id, composite_id)
    if not blockers:
        return ImpactReport(can_remove=True)
    return ImpactReport(
        can_remove=False,
        reasons=[f"{len(blockers)} open trade(s) reference this composite"],
        blocking_trades=blockers,
        suggested_action="disable",
    )


def compute_strategy_exchange_impact(
    db: Session, strategy_id: uuid.UUID, exchange_id: uuid.UUID
) -> ImpactReport:
    blocking_trades = _non_terminal_trades_for_exchange_assignment(db, strategy_id, exchange_id)
    blocking_scope = _orphaned_universe_items_if_remove_exchange(db, strategy_id, exchange_id)
    if not blocking_trades and not blocking_scope:
        return ImpactReport(can_remove=True)

    reasons: list[str] = []
    if blocking_trades:
        reasons.append(f"{len(blocking_trades)} open trade(s) routed via this exchange")
    if blocking_scope:
        reasons.append(
            f"{len(blocking_scope)} active universe item(s) would be left without a tradeable exchange"
        )
    suggestion = "disable" if blocking_trades and not blocking_scope else "clear_blockers"
    return ImpactReport(
        can_remove=False,
        reasons=reasons,
        blocking_trades=blocking_trades,
        blocking_scope_items=blocking_scope,
        suggested_action=suggestion,
    )


def compute_feed_universe_impact(
    db: Session, feed_id: uuid.UUID, instrument_id: uuid.UUID
) -> ImpactReport:
    blocking_trades = _trades_blocking_feed_disable(db, feed_id, instrument_id)
    blocking_scope = _strategy_universe_items_depending_on_feed(
        db, feed_id, instrument_id, scope_type="strategy_universe"
    )
    if not blocking_trades and not blocking_scope:
        return ImpactReport(can_remove=True)

    reasons: list[str] = []
    if blocking_trades:
        reasons.append(f"{len(blocking_trades)} open trade(s) need price data from this feed")
    if blocking_scope:
        reasons.append(
            f"{len(blocking_scope)} strategy universe item(s) depend on this feed coverage"
        )
    return ImpactReport(
        can_remove=False,
        reasons=reasons,
        blocking_trades=blocking_trades,
        blocking_scope_items=blocking_scope,
        suggested_action="clear_blockers",
    )


def compute_feed_composite_universe_impact(
    db: Session, feed_id: uuid.UUID, composite_id: uuid.UUID
) -> ImpactReport:
    blocking_trades = _trades_blocking_feed_composite_disable(db, feed_id, composite_id)
    blocking_scope = _strategy_universe_items_depending_on_feed(
        db, feed_id, composite_id, scope_type="strategy_composite_universe"
    )
    if not blocking_trades and not blocking_scope:
        return ImpactReport(can_remove=True)

    reasons: list[str] = []
    if blocking_trades:
        reasons.append(f"{len(blocking_trades)} open composite trade(s) need data from this feed")
    if blocking_scope:
        reasons.append(
            f"{len(blocking_scope)} strategy composite universe item(s) depend on this feed"
        )
    return ImpactReport(
        can_remove=False,
        reasons=reasons,
        blocking_trades=blocking_trades,
        blocking_scope_items=blocking_scope,
        suggested_action="clear_blockers",
    )


def _strategy_universe_items_depending_on_feed(
    db: Session,
    feed_id: uuid.UUID,
    target_id: uuid.UUID,
    *,
    scope_type: str,
) -> list[BlockingScopeItem]:
    """Active strategy universe items pointing at ``target_id`` whose strategy
    uses this feed (and has no other feed covering the same target).
    """
    strategy_ids = set(
        db.execute(
            select(StrategyFeed.strategy_id).where(StrategyFeed.feed_id == feed_id)
        ).scalars()
    )
    if not strategy_ids:
        return []

    if scope_type == "strategy_composite_universe":
        rows = db.execute(
            select(StrategyCompositeScope.strategy_id, StrategyCompositeScope.composite_id)
            .where(StrategyCompositeScope.strategy_id.in_(strategy_ids))
            .where(StrategyCompositeScope.composite_id == target_id)
            .where(StrategyCompositeScope.dropped_at.is_(None))
        ).all()
        return [
            BlockingScopeItem(
                scope_type="strategy_composite_universe",
                strategy_id=sid,
                composite_id=cid,
            )
            for sid, cid in rows
        ]

    rows = db.execute(
        select(StrategyInstrumentScope.strategy_id, StrategyInstrumentScope.instrument_id)
        .where(StrategyInstrumentScope.strategy_id.in_(strategy_ids))
        .where(StrategyInstrumentScope.instrument_id == target_id)
        .where(StrategyInstrumentScope.dropped_at.is_(None))
    ).all()
    return [
        BlockingScopeItem(
            scope_type="strategy_universe",
            strategy_id=sid,
            instrument_id=iid,
        )
        for sid, iid in rows
    ]


# ---------------------------------------------------------------------------
# Strategy-exchange disable / remove
# ---------------------------------------------------------------------------


def set_strategy_exchange_active(
    db: Session, strategy_id: uuid.UUID, exchange_id: uuid.UUID, is_active: bool
) -> StrategyExchange:
    scope = db.get(StrategyExchange, (strategy_id, exchange_id))
    if not scope:
        raise NotFoundError("Strategy-exchange link not found")
    scope.is_active = is_active
    db.commit()
    db.refresh(scope)
    return scope


def remove_strategy_exchange_with_impact_check(
    db: Session, strategy_id: uuid.UUID, exchange_id: uuid.UUID
) -> None:
    """Drop-in replacement for :func:`strategy_service.remove_strategy_exchange`
    that raises :class:`ConflictError` when blocked.
    """
    scope = db.get(StrategyExchange, (strategy_id, exchange_id))
    if not scope:
        raise NotFoundError("Strategy-exchange link not found")
    impact = compute_strategy_exchange_impact(db, strategy_id, exchange_id)
    if not impact.can_remove:
        raise ConflictError(_format_impact_message(impact))
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Strategy pause
# ---------------------------------------------------------------------------


def set_strategy_paused(db: Session, strategy_id: uuid.UUID, is_paused: bool) -> StrategyModel:
    """Pausing is always allowed; resume is too. Per the design, this never
    blocks — open trades exit normally regardless.
    """
    strategy = db.get(StrategyModel, strategy_id)
    if not strategy:
        raise NotFoundError(f"Strategy {strategy_id} not found")
    strategy.is_paused = is_paused
    db.commit()
    db.refresh(strategy)
    return strategy


# ---------------------------------------------------------------------------
# Startup reconciliation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DriftItem:
    scope_type: str  # "strategy_universe" | "strategy_composite_universe"
    strategy_id: uuid.UUID
    item_id: uuid.UUID
    reason: str


def reconcile_strategy_universe(db: Session, strategy_id: uuid.UUID) -> list[_DriftItem]:
    """Detect drifted active scope rows and disable them.

    A strategy universe item has drifted iff it's ``is_active=True`` but:
      - instrument's ``(provider_id, instrument_type_id)`` doesn't match any
        of the strategy's active exchanges, OR
      - instrument isn't covered by any of the strategy's feeds' active scope.

    A composite universe item has drifted iff it's ``is_active=True`` but:
      - any member fails the exchange-pair check above, OR
      - the composite isn't in any of the strategy's feeds' active composite scope.

    Each drifted row is flipped to ``is_active=False`` and returned for logging.
    Removed rows are committed as a single transaction at the end.
    """
    drift: list[_DriftItem] = []

    tradeable_pairs = _get_strategy_tradeable_pairs(db, strategy_id)
    fed_instrument_ids = _get_strategy_feed_instrument_ids(db, strategy_id)
    fed_composite_ids = _get_strategy_feed_composite_ids(db, strategy_id)

    instrument_scopes = (
        db.execute(
            select(StrategyInstrumentScope)
            .where(StrategyInstrumentScope.strategy_id == strategy_id)
            .where(StrategyInstrumentScope.dropped_at.is_(None))
            .options(joinedload(StrategyInstrumentScope.instrument))
        )
        .unique()
        .scalars()
        .all()
    )
    for scope in instrument_scopes:
        inst = scope.instrument
        if inst is None:
            continue
        reason: str | None = None
        if (inst.provider_id, inst.instrument_type_id) not in tradeable_pairs:
            reason = "no strategy exchange matches (provider, type)"
        elif inst.id not in fed_instrument_ids:
            reason = "instrument not in any strategy feed's active scope"
        if reason is not None:
            scope.dropped_at = datetime.now(UTC)
            drift.append(
                _DriftItem(
                    scope_type="strategy_universe",
                    strategy_id=strategy_id,
                    item_id=inst.id,
                    reason=reason,
                )
            )

    composite_scopes = (
        db.execute(
            select(StrategyCompositeScope)
            .where(StrategyCompositeScope.strategy_id == strategy_id)
            .where(StrategyCompositeScope.dropped_at.is_(None))
            .options(joinedload(StrategyCompositeScope.composite))
        )
        .unique()
        .scalars()
        .all()
    )
    for scope in composite_scopes:
        comp_id = scope.composite_id
        reason = None
        members = db.execute(
            select(Instrument.id, Instrument.provider_id, Instrument.instrument_type_id)
            .join(CompositeMember, CompositeMember.instrument_id == Instrument.id)
            .where(CompositeMember.composite_id == comp_id)
        ).all()
        if not members:
            reason = "composite has no members"
        else:
            untradeable = [
                m for m in members if (m.provider_id, m.instrument_type_id) not in tradeable_pairs
            ]
            if untradeable:
                reason = "composite has member(s) not tradeable on any strategy exchange"
            elif comp_id not in fed_composite_ids:
                reason = "composite not in any strategy feed's active composite scope"
        if reason is not None:
            scope.dropped_at = datetime.now(UTC)
            drift.append(
                _DriftItem(
                    scope_type="strategy_composite_universe",
                    strategy_id=strategy_id,
                    item_id=comp_id,
                    reason=reason,
                )
            )

    if drift:
        db.commit()
    return drift
