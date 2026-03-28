import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    StrategyAssetScope,
)
from ascent.database.models.feeds import FeedAssetScope
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.universe import UniverseItemCreate, UniverseItemSchema
from ascent.server.services.provider_asset_service import get_or_create_single_member_group

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_item(scope) -> UniverseItemSchema:
    return UniverseItemSchema(
        provider_id=scope.provider_id,
        provider_name=scope.provider.name if scope.provider else None,
        from_asset_id=scope.from_asset_id,
        from_asset_symbol=(
            scope.from_asset.symbol or scope.from_asset.name if scope.from_asset else None
        ),
        to_asset_id=scope.to_asset_id,
        to_asset_symbol=(scope.to_asset.symbol or scope.to_asset.name if scope.to_asset else None),
        provider_asset_group_id=scope.provider_asset_group_id,
        order=scope.order,
    )


def _resolve_group_id(db: Session, data: UniverseItemCreate) -> uuid.UUID:
    """Return the group ID from the request, or auto-create a single-member group."""
    if data.provider_asset_group_id is not None:
        return data.provider_asset_group_id
    group = get_or_create_single_member_group(
        db, data.provider_id, data.from_asset_id, data.to_asset_id
    )
    return group.id


# ---------------------------------------------------------------------------
# Strategy Universe
# ---------------------------------------------------------------------------


def get_strategy_universe(db: Session, strategy_id: uuid.UUID) -> list[UniverseItemSchema]:
    query = (
        select(StrategyAssetScope)
        .where(StrategyAssetScope.strategy_id == strategy_id)
        .options(
            joinedload(StrategyAssetScope.provider),
            joinedload(StrategyAssetScope.from_asset),
            joinedload(StrategyAssetScope.to_asset),
        )
        .order_by(StrategyAssetScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()

    return [_build_item(s) for s in scopes]


def add_strategy_universe_item(
    db: Session, strategy_id: uuid.UUID, data: UniverseItemCreate
) -> StrategyAssetScope:
    group_id = _resolve_group_id(db, data)
    scope = StrategyAssetScope(
        strategy_id=strategy_id,
        provider_id=data.provider_id,
        from_asset_id=data.from_asset_id,
        to_asset_id=data.to_asset_id,
        provider_asset_group_id=group_id,
        order=data.order,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_strategy_universe_item(
    db: Session,
    strategy_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
) -> None:
    scope = db.get(
        StrategyAssetScope,
        (strategy_id, provider_id, from_asset_id, to_asset_id),
    )
    if not scope:
        raise NotFoundError("Universe item not found")
    db.delete(scope)
    db.commit()


# ---------------------------------------------------------------------------
# Feed Universe
# ---------------------------------------------------------------------------


def get_feed_universe(db: Session, feed_id: uuid.UUID) -> list[UniverseItemSchema]:
    query = (
        select(FeedAssetScope)
        .where(FeedAssetScope.feed_id == feed_id)
        .options(
            joinedload(FeedAssetScope.provider),
            joinedload(FeedAssetScope.from_asset),
            joinedload(FeedAssetScope.to_asset),
        )
        .order_by(FeedAssetScope.order)
    )
    scopes = db.execute(query).unique().scalars().all()

    return [_build_item(s) for s in scopes]


def add_feed_universe_item(
    db: Session, feed_id: uuid.UUID, data: UniverseItemCreate
) -> FeedAssetScope:
    group_id = _resolve_group_id(db, data)
    scope = FeedAssetScope(
        feed_id=feed_id,
        provider_id=data.provider_id,
        from_asset_id=data.from_asset_id,
        to_asset_id=data.to_asset_id,
        provider_asset_group_id=group_id,
        order=data.order,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_feed_universe_item(
    db: Session,
    feed_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
) -> None:
    scope = db.get(
        FeedAssetScope,
        (feed_id, provider_id, from_asset_id, to_asset_id),
    )
    if not scope:
        raise NotFoundError("Universe item not found")
    db.delete(scope)
    db.commit()
