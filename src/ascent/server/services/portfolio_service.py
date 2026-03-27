import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Portfolio
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.portfolios import PortfolioCreate, PortfolioSchema, PortfolioUpdate


def get_portfolios(db: Session) -> list[PortfolioSchema]:
    query = select(Portfolio).options(joinedload(Portfolio.base_currency_asset))
    portfolios = db.execute(query).unique().scalars().all()
    return [
        PortfolioSchema(
            id=p.id,
            name=p.name,
            description=p.description,
            base_currency=(
                p.base_currency_asset.symbol or p.base_currency_asset.name
                if p.base_currency_asset
                else None
            ),
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in portfolios
    ]


def create_portfolio(db: Session, data: PortfolioCreate) -> Portfolio:
    portfolio = Portfolio(**data.model_dump())
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def update_portfolio(db: Session, portfolio_id: uuid.UUID, data: PortfolioUpdate) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if not portfolio:
        raise NotFoundError("Portfolio not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(portfolio, key, value)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def delete_portfolio(db: Session, portfolio_id: uuid.UUID) -> None:
    portfolio = db.get(Portfolio, portfolio_id)
    if not portfolio:
        raise NotFoundError("Portfolio not found")
    db.delete(portfolio)
    db.commit()
