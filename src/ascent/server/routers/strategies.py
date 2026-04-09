import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.feeds import StrategyFeedItem
from ascent.server.schemas.orders import OrderSchema
from ascent.server.schemas.strategies import (
    StrategyCreate,
    StrategyDetail,
    StrategyFeedCreate,
    StrategyFeedDAG,
    StrategyListItem,
    StrategyRunListItem,
    StrategyStats,
    StrategyUpdate,
)
from ascent.server.schemas.trades import TradeListItem
from ascent.server.schemas.universe import (
    CompositeUniverseBatchAdd,
    CompositeUniverseItemSchema,
    UniverseBatchAddInstruments,
    UniverseItemCreate,
    UniverseItemSchema,
)
from ascent.server.services import order_service, strategy_service, trade_service, universe_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=PaginatedResponse[StrategyListItem])
def list_strategies(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    items, total = strategy_service.get_strategies(
        db, page=page, page_size=page_size, search=search, is_active=is_active
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages
    )


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


@router.get("/{strategy_id}/stats", response_model=StrategyStats)
def get_strategy_stats(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return strategy_service.get_strategy_stats(db, strategy_id)


@router.get("/{strategy_id}/feeds", response_model=StrategyFeedDAG)
def get_strategy_feeds(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return strategy_service.get_strategy_feed_dag(db, strategy_id)


@router.post("/{strategy_id}/feeds", status_code=201, response_model=StrategyFeedItem)
def add_strategy_feed(
    strategy_id: uuid.UUID, data: StrategyFeedCreate, db: Session = Depends(get_db)
):
    return strategy_service.add_strategy_feed(db, strategy_id, data)


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


@router.get("/{strategy_id}/orders", response_model=PaginatedResponse[OrderSchema])
def get_strategy_orders(
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    items, total = order_service.get_strategy_orders(
        db, strategy_id, page=page, page_size=page_size
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
    "/{strategy_id}/universe/{instrument_id}",
    status_code=204,
)
def remove_strategy_universe_item(
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    universe_service.remove_strategy_universe_item(db, strategy_id, instrument_id)


@router.post("/{strategy_id}/universe/batch", response_model=list[UniverseItemSchema])
def batch_add_strategy_instruments(
    strategy_id: uuid.UUID, data: UniverseBatchAddInstruments, db: Session = Depends(get_db)
):
    return universe_service.batch_add_strategy_instruments(db, strategy_id, data)


# ---- Composite Universe ----


@router.get("/{strategy_id}/composite-universe", response_model=list[CompositeUniverseItemSchema])
def list_strategy_composite_universe(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    return universe_service.get_strategy_composite_universe(db, strategy_id)


@router.post(
    "/{strategy_id}/composite-universe/batch", response_model=list[CompositeUniverseItemSchema]
)
def batch_add_strategy_composites(
    strategy_id: uuid.UUID, data: CompositeUniverseBatchAdd, db: Session = Depends(get_db)
):
    return universe_service.batch_add_strategy_composites(db, strategy_id, data)


@router.delete("/{strategy_id}/composite-universe/{composite_id}", status_code=204)
def remove_strategy_composite_universe_item(
    strategy_id: uuid.UUID, composite_id: uuid.UUID, db: Session = Depends(get_db)
):
    universe_service.remove_strategy_composite_universe_item(db, strategy_id, composite_id)


@router.get("/{strategy_id}/runs/{run_id}", response_model=StrategyRunListItem)
def get_strategy_run(strategy_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    return strategy_service.get_strategy_run(db, strategy_id, run_id)


@router.get("/{strategy_id}/runs", response_model=PaginatedResponse[StrategyRunListItem])
def list_strategy_runs(
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = strategy_service.get_strategy_runs(
        db,
        strategy_id,
        page=page,
        page_size=page_size,
        started_after=started_after,
        started_before=started_before,
        status=status,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
