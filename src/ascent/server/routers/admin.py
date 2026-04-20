from fastapi import APIRouter, Depends
from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from ascent.database.models import StrategyRun
from ascent.database.models.composites import CompositeAttribute
from ascent.database.models.feeds import FeedRun
from ascent.database.models.instruments import InstrumentAttribute
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
from ascent.server.dependencies import engine, get_db
from ascent.server.schemas.admin import (
    CompositeAttributeBatchCreate,
    FeedRunCreate,
    FeedRunSchema,
    InstrumentAttributeBatchCreate,
    StrategyRunCreate,
    StrategyRunFeedRunCreate,
    StrategyRunFeedRunSchema,
    StrategyRunSchema,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/reset-pool")
def reset_pool():
    """Dispose the SQLAlchemy connection pool, forcing fresh connections."""
    engine.dispose()
    return {"status": "ok"}


@router.post("/reset-database")
def drop_and_recreate():
    """Drop all tables and recreate them. Used by the seed command."""
    from ascent.server.main import _create_tables

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.commit()
    engine.dispose()
    _create_tables()
    return {"status": "ok"}


@router.post("/feed-runs", status_code=201, response_model=FeedRunSchema)
def create_feed_run(data: FeedRunCreate, db: Session = Depends(get_db)):
    obj = FeedRun(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/strategy-runs", status_code=201, response_model=StrategyRunSchema)
def create_strategy_run(data: StrategyRunCreate, db: Session = Depends(get_db)):
    obj = StrategyRun(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/strategy-run-feed-runs", status_code=201, response_model=StrategyRunFeedRunSchema)
def create_strategy_run_feed_run(data: StrategyRunFeedRunCreate, db: Session = Depends(get_db)):
    obj = StrategyRunFeedRun(**data.model_dump())
    db.add(obj)
    db.commit()
    return obj


@router.post("/instrument-attributes/batch", status_code=201)
def batch_create_instrument_attributes(
    data: InstrumentAttributeBatchCreate, db: Session = Depends(get_db)
):
    if not data.entries:
        return {"count": 0}
    rows = [e.model_dump() for e in data.entries]
    db.execute(insert(InstrumentAttribute).values(rows))
    db.commit()
    return {"count": len(rows)}


@router.post("/composite-attributes/batch", status_code=201)
def batch_create_composite_attributes(
    data: CompositeAttributeBatchCreate, db: Session = Depends(get_db)
):
    if not data.entries:
        return {"count": 0}
    rows = [e.model_dump() for e in data.entries]
    db.execute(insert(CompositeAttribute).values(rows))
    db.commit()
    return {"count": len(rows)}
