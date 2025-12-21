import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, func, mapped_column, relationship

from summit.database.models.assets import Asset
from summit.database.models.base import Base

if TYPE_CHECKING:
    from summit.database.models.transactions import Transaction


class Portfolio(Base):
    __tablename__ = "portfolio"
    __table_args__ = {
        "comment": "The portfolio, represents a collection of assets and their transactions for tracking investment strategies and performance."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the portfolio"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the portfolio"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the portfolio"
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the portfolio is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the portfolio",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the portfolio",
    )

    # Relationship to transactions
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="portfolio"
    )

    # Relationship to positions
    holdings: Mapped[list["PortfolioAssetHolding"]] = relationship(
        "PortfolioAssetHolding", back_populates="portfolio"
    )

    def __repr__(self):
        return f"{Portfolio.__name__}({self.id}, {self.name})"


class PortfolioAssetHolding(Base):
    __tablename__ = "portfolio_asset_holding"
    __table_args__ = {
        "comment": "Stores position snapshots (holdings) for each portfolio over time. This is the position book of record that should reconcile with the transaction book (portfolio_transaction). Maintains two books of record for data integrity and reconciliation purposes. Tracks position history through time-series snapshots."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        comment="The timestamp when this position snapshot is valid. Part of the primary key to enable time-series position tracking and historical reconciliation.",
    )
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the portfolio",
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the asset",
    )
    asset: Mapped["Asset"] = relationship("Asset")
    quantity: Mapped[float] = mapped_column(
        nullable=False,
        comment="The quantity/shares held at this timestamp. Can be positive for long positions or negative for short positions.",
    )
    average_cost: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The average cost per unit for this position at this timestamp. Used for calculating unrealized P&L. Calculated as the weighted average of all purchase prices.",
    )
    last_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id"),
        nullable=True,
        comment="The identifier of the last transaction that updated this position. Used for reconciliation and audit trail purposes.",
    )
    last_transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", foreign_keys=[last_transaction_id]
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the position record",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the position record",
    )

    def __repr__(self):
        return f"{PortfolioAssetHolding.__name__}(timestamp={self.timestamp}, portfolio_id={self.portfolio_id}, asset_id={self.asset_id}, quantity={self.quantity}, average_cost={self.average_cost})"
