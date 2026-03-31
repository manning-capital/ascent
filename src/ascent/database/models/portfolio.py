import datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.providers import Provider

if TYPE_CHECKING:
    from ascent.database.models.transactions import Transaction


class Portfolio(NamedEntityMixin, Base):
    __tablename__ = "portfolio"
    __table_args__ = {
        "comment": "The portfolio, represents a collection of assets and their transactions for tracking investment strategies and performance."
    }

    base_currency_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
    )
    base_currency_asset: Mapped[Optional["Asset"]] = relationship(
        "Asset", foreign_keys="[Portfolio.base_currency_asset_id]"
    )
    pricing_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
    )
    pricing_provider: Mapped[Optional["Provider"]] = relationship("Provider")

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="portfolio"
    )
    holdings: Mapped[list["PortfolioAssetHolding"]] = relationship(
        "PortfolioAssetHolding", back_populates="portfolio"
    )


class PortfolioAssetHolding(Base):
    __tablename__ = "portfolio_asset_holding"
    __table_args__ = {
        "comment": "Stores position snapshots (holdings) for each portfolio over time."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(primary_key=True, nullable=False)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolio.id"),
        primary_key=True,
        nullable=False,
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
    )
    asset: Mapped["Asset"] = relationship("Asset")
    quantity: Mapped[float] = mapped_column(nullable=False)
    average_cost: Mapped[float | None] = mapped_column(nullable=True)
    last_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transaction.id"),
        nullable=True,
    )
    last_transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", foreign_keys=[last_transaction_id]
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
    )
