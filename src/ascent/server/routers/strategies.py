import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.strategies import (
    StrategyCreate,
    StrategyDetail,
    StrategyFeedDAG,
    StrategyListItem,
    StrategyRunListItem,
    StrategyUpdate,
)
from ascent.server.schemas.trades import TradeListItem
from ascent.server.schemas.universe import UniverseItemCreate, UniverseItemSchema
from ascent.server.services import strategy_service, trade_service, universe_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyListItem])
def list_strategies(db: Session = Depends(get_db)):
    return strategy_service.get_strategies(db)


@router.post("", status_code=201)
def create_strategy(data: StrategyCreate, db: Session = Depends(get_db)):
    return strategy_service.create_strategy(db, data)


@router.get("/{strategy_id}", response_model=StrategyDetail)
def get_strategy(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return strategy_service.get_strategy_detail(db, strategy_id)


@router.put("/{strategy_id}")
def update_strategy(strategy_id: uuid.UUID, data: StrategyUpdate, db: Session = Depends(get_db)):
    return strategy_service.update_strategy(db, strategy_id, data)


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    strategy_service.delete_strategy(db, strategy_id)


@router.get("/{strategy_id}/feeds", response_model=StrategyFeedDAG)
def get_strategy_feeds(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return strategy_service.get_strategy_feed_dag(db, strategy_id)


@router.get("/{strategy_id}/parameter-schema")
def get_strategy_parameter_schema(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    strategy = strategy_service.get_strategy_detail(db, strategy_id)
    return strategy.parameter_schema or {}


@router.get("/{strategy_id}/trades", response_model=PaginatedResponse[TradeListItem])
def get_strategy_trades(
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    items, total = trade_service.get_trades(
        db, strategy_id=strategy_id, page=page, page_size=page_size
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{strategy_id}/universe", response_model=list[UniverseItemSchema])
def get_strategy_universe(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return universe_service.get_strategy_universe(db, strategy_id)


@router.post("/{strategy_id}/universe", status_code=201)
def add_strategy_universe_item(
    strategy_id: uuid.UUID, data: UniverseItemCreate, db: Session = Depends(get_db)
):
    return universe_service.add_strategy_universe_item(db, strategy_id, data)


@router.delete(
    "/{strategy_id}/universe/{provider_id}/{from_asset_id}/{to_asset_id}",
    status_code=204,
)
def remove_strategy_universe_item(
    strategy_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    universe_service.remove_strategy_universe_item(
        db, strategy_id, provider_id, from_asset_id, to_asset_id
    )


@router.get("/{strategy_id}/runs", response_model=PaginatedResponse[StrategyRunListItem])
def list_strategy_runs(
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = strategy_service.get_strategy_runs(
        db,
        strategy_id,
        page=page,
        page_size=page_size,
        started_after=started_after,
        started_before=started_before,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
