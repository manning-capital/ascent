import asyncio
import datetime
import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from ascent.engine.cache import EngineCache
from ascent.server.dependencies import engine as db_engine
from ascent.server.dependencies import get_cache, get_db
from ascent.server.schemas.common import PaginatedResponse
from ascent.server.schemas.trades import (
    TradeConditionCreate,
    TradeCreate,
    TradeDataSeriesCreate,
    TradeDetail,
    TradeLegCreate,
    TradeLegUpdate,
    TradeListItem,
    TradeSnapshotCreate,
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
    sort_field: str = "entry_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 25,
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
        sort_field=sort_field,
        sort_order=sort_order,
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


@router.get("/stream")
async def stream_trades(cache: EngineCache = Depends(get_cache)):
    """SSE endpoint that streams real-time trade updates.

    Subscribes to the ``ascent.trades.updates`` Redis channel and
    streams enriched ``TradeListItem`` payloads as they change.
    """

    async def event_generator():
        pubsub = cache.subscribe(["ascent.trades.updates"])
        try:
            while True:
                msg = await asyncio.to_thread(cache.poll, pubsub, 5.0)
                if msg is None:
                    yield ": keepalive\n\n"
                    continue
                trade_id_str = msg.get("trade_id")
                if not trade_id_str:
                    continue
                try:
                    tid = uuid.UUID(trade_id_str)
                except ValueError:
                    continue
                with Session(db_engine) as db:
                    item = trade_service.get_trade_list_item_by_id(db, tid)
                if item is None:
                    continue
                payload = json.dumps(
                    item.model_dump(mode="json"),
                    default=str,
                )
                yield f"event: trade_update\ndata: {payload}\n\n"
        finally:
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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


@router.post("/{trade_id}/conditions", status_code=201)
def add_trade_condition(
    trade_id: uuid.UUID, data: TradeConditionCreate, db: Session = Depends(get_db)
):
    return trade_service.add_trade_condition(db, trade_id, data)


@router.post("/{trade_id}/snapshots", status_code=201)
def add_trade_snapshot(
    trade_id: uuid.UUID, data: TradeSnapshotCreate, db: Session = Depends(get_db)
):
    return trade_service.add_trade_snapshot(db, trade_id, data)


@router.post("/{trade_id}/data-series", status_code=201)
def add_trade_data_series(
    trade_id: uuid.UUID, data: TradeDataSeriesCreate, db: Session = Depends(get_db)
):
    return trade_service.add_trade_data_series(db, trade_id, data)
