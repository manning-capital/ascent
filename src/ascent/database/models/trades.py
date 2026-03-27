import datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.portfolio import Portfolio
from ascent.database.models.types import TradeStatusType

if TYPE_CHECKING:
    from ascent.database.models.orders import Order
    from ascent.database.models.strategy import Strategy, StrategyRun
    from ascent.database.models.trade_analysis import (
        TradeCondition,
        TradeDataSeries,
        TradeSnapshot,
    )
    from ascent.database.models.transactions import TransactionGroup


class Trade(Base):
    __tablename__ = "trade"
    __table_args__ = {
        "comment": "Represents a trade decision made by a trading strategy. A trade can contain multiple legs (for multi-asset strategies like pairs trading). Tracks the full lifecycle from entry to exit, including paper trading support."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the trade"
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        nullable=False,
        comment="The identifier of the strategy that generated this trade",
    )
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="trades")
    strategy_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("strategy_run.id"),
        nullable=True,
        comment="The identifier of the strategy run that created this trade. Nullable because a trade may span multiple runs or be created manually.",
    )
    strategy_run: Mapped[Optional["StrategyRun"]] = relationship("StrategyRun")
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolio.id"),
        nullable=False,
        comment="The identifier of the portfolio this trade belongs to",
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio")
    is_paper: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether this is a paper/simulated trade (True) or a live trade (False)",
    )
    entry_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True,
        comment="The timestamp when the trade was entered/opened",
    )
    exit_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True,
        comment="The timestamp when the trade was exited/closed. Null for open trades.",
    )
    close_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="The reason the trade was closed, e.g. MODEL_SIGNAL, MANUAL, STOP_LOSS, TAKE_PROFIT, ERROR",
    )
    current_status_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("trade_status_type.id"),
        nullable=True,
        comment="The current status type of the trade. Denormalized from TradeStatus for efficient querying.",
    )
    current_status_type: Mapped[Optional["TradeStatusType"]] = relationship("TradeStatusType")
    parameters: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Strategy-specific data stored as JSONB. Contains non-queryable information about the trade context.",
    )
    total_realized_pnl: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The total realized P&L for this trade across all legs. Denormalized for query performance.",
    )
    total_unrealized_pnl: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The total unrealized P&L for this trade across all legs. Updated periodically.",
    )
    total_fees: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The total fees paid for this trade across all legs and transactions.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the trade record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the trade record",
    )

    # Relationships
    legs: Mapped[list["TradeLeg"]] = relationship(
        "TradeLeg", back_populates="trade", cascade="all, delete-orphan"
    )
    statuses: Mapped[list["TradeStatus"]] = relationship(
        "TradeStatus", back_populates="trade", order_by="TradeStatus.timestamp.asc()"
    )
    conditions: Mapped[list["TradeCondition"]] = relationship(
        "TradeCondition", back_populates="trade", cascade="all, delete-orphan"
    )
    data_series: Mapped[list["TradeDataSeries"]] = relationship(
        "TradeDataSeries", back_populates="trade", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["TradeSnapshot"]] = relationship(
        "TradeSnapshot", back_populates="trade", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"{Trade.__name__}(id={self.id}, strategy_id={self.strategy_id}, portfolio_id={self.portfolio_id}, is_paper={self.is_paper})"


class TradeLeg(Base):
    __tablename__ = "trade_leg"
    __table_args__ = {
        "comment": "Represents an individual asset leg within a trade. For a pairs trade, there would be two legs (one long, one short). Each leg tracks entry/exit prices, orders, and transactions including partial fills."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the trade leg"
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade.id"),
        nullable=False,
        comment="The identifier of the trade this leg belongs to",
    )
    trade: Mapped["Trade"] = relationship("Trade", back_populates="legs")
    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the from asset (base asset). Matches the ProviderAssetAttribute convention.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the to asset (quote asset). Matches the ProviderAssetAttribute convention.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="The direction of this trade leg: LONG or SHORT",
    )
    quantity: Mapped[float] = mapped_column(
        nullable=False,
        comment="The number of units/shares in this trade leg",
    )
    expected_entry_price: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The expected price at entry (signal price). Used for slippage calculation: slippage = entry_price - expected_entry_price.",
    )
    entry_price: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The actual price at which this leg was entered. Null for pending legs. May be a volume-weighted average across partial fills.",
    )
    expected_exit_price: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The expected price at exit. Used for slippage calculation.",
    )
    exit_price: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The actual price at which this leg was exited. Null for open or pending legs.",
    )
    entry_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("order.id"),
        nullable=True,
        comment="The identifier of the order submitted to open this leg. Null if not yet submitted.",
    )
    entry_order: Mapped[Optional["Order"]] = relationship("Order", foreign_keys=[entry_order_id])
    exit_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("order.id"),
        nullable=True,
        comment="The identifier of the order submitted to close this leg. Null if not yet submitted.",
    )
    exit_order: Mapped[Optional["Order"]] = relationship("Order", foreign_keys=[exit_order_id])
    entry_transaction_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transaction_group.id"),
        nullable=True,
        comment="The identifier of the transaction group containing entry fill transactions. Supports partial fills.",
    )
    entry_transaction_group: Mapped[Optional["TransactionGroup"]] = relationship(
        "TransactionGroup", foreign_keys=[entry_transaction_group_id]
    )
    exit_transaction_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transaction_group.id"),
        nullable=True,
        comment="The identifier of the transaction group containing exit fill transactions. Supports partial fills.",
    )
    exit_transaction_group: Mapped[Optional["TransactionGroup"]] = relationship(
        "TransactionGroup", foreign_keys=[exit_transaction_group_id]
    )
    realized_pnl: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The realized P&L for this leg. Computed from entry/exit prices, quantity, and fees.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the trade leg record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the trade leg record",
    )

    def __repr__(self):
        return f"{TradeLeg.__name__}(id={self.id}, trade_id={self.trade_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, direction={self.direction}, quantity={self.quantity})"


class TradeStatus(Base):
    __tablename__ = "trade_status"
    __table_args__ = {
        "comment": "Time series table storing status updates for trades. Tracks the status history of trades over time, allowing for audit trails and status change monitoring."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp when the status was recorded",
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the trade",
    )
    trade: Mapped["Trade"] = relationship("Trade", back_populates="statuses")
    trade_status_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade_status_type.id"),
        nullable=False,
        comment="The identifier of the trade status type",
    )
    trade_status_type: Mapped["TradeStatusType"] = relationship("TradeStatusType")

    def __repr__(self):
        return f"{TradeStatus.__name__}(timestamp={self.timestamp}, trade_id={self.trade_id}, trade_status_type_id={self.trade_status_type_id})"
