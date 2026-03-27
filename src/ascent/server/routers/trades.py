import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.trades import (
    TradeCreate,
    TradeDetail,
    TradeLegCreate,
    TradeLegUpdate,
    TradeListItem,
    TradeStatusCreate,
    TradeUpdate,
)
from ascent.server.services import trade_service

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=PaginatedResponse[TradeListItem])
def list_trades(
    status: str | None = None,
    strategy_id: uuid.UUID | None = None,
    search: str | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    tags: list[str] | None = Query(None),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    items, total = trade_service.get_trades(
        db,
        status=status,
        strategy_id=strategy_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        tags=tags,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", status_code=201)
def create_trade(data: TradeCreate, db: Session = Depends(get_db)):
    return trade_service.create_trade(db, data)


@router.get("/{trade_id}", response_model=TradeDetail)
def get_trade(trade_id: uuid.UUID, db: Session = Depends(get_db)):
    return trade_service.get_trade_detail(db, trade_id)


@router.put("/{trade_id}")
def update_trade(trade_id: uuid.UUID, data: TradeUpdate, db: Session = Depends(get_db)):
    return trade_service.update_trade(db, trade_id, data)


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: uuid.UUID, db: Session = Depends(get_db)):
    trade_service.delete_trade(db, trade_id)


@router.post("/{trade_id}/legs", status_code=201)
def add_trade_leg(trade_id: uuid.UUID, data: TradeLegCreate, db: Session = Depends(get_db)):
    return trade_service.add_trade_leg(db, trade_id, data)


@router.put("/legs/{leg_id}")
def update_trade_leg(leg_id: uuid.UUID, data: TradeLegUpdate, db: Session = Depends(get_db)):
    return trade_service.update_trade_leg(db, leg_id, data)


@router.delete("/legs/{leg_id}", status_code=204)
def delete_trade_leg(leg_id: uuid.UUID, db: Session = Depends(get_db)):
    trade_service.delete_trade_leg(db, leg_id)


@router.post("/{trade_id}/statuses", status_code=201)
def add_trade_status(trade_id: uuid.UUID, data: TradeStatusCreate, db: Session = Depends(get_db)):
    return trade_service.add_trade_status(db, trade_id, data)
