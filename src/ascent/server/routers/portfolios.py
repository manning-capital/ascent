import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.portfolios import PortfolioCreate, PortfolioSchema, PortfolioUpdate
from ascent.server.services import portfolio_service

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioSchema])
def list_portfolios(db: Session = Depends(get_db)):
    return portfolio_service.get_portfolios(db)


@router.post("", status_code=201)
def create_portfolio(data: PortfolioCreate, db: Session = Depends(get_db)):
    return portfolio_service.create_portfolio(db, data)


@router.put("/{portfolio_id}")
def update_portfolio(portfolio_id: uuid.UUID, data: PortfolioUpdate, db: Session = Depends(get_db)):
    return portfolio_service.update_portfolio(db, portfolio_id, data)


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)):
    portfolio_service.delete_portfolio(db, portfolio_id)
