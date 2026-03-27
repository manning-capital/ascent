import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.portfolio import Portfolio
from ascent.database.models.providers import Provider
from ascent.database.models.types import StrategyType

if TYPE_CHECKING:
    from ascent.database.models.feeds import StrategyFeed
    from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
    from ascent.database.models.trades import Trade


class Strategy(Base):
    __tablename__ = "strategy"
    __table_args__ = {
        "comment": "Represents a registered trading strategy. Stores the strategy configuration, importable class path, and JSONB parameters. Each strategy is associated with a portfolio for executing trades."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the strategy"
    )
    strategy_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy_type.id"),
        nullable=False,
        comment="The identifier of the strategy type",
    )
    strategy_type: Mapped["StrategyType"] = relationship("StrategyType")
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the strategy"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the strategy"
    )
    strategy_ref: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="The fully qualified importable Python path to the strategy function, e.g. 'ascent.strategies.examples.pairs:pairs_strategy'",
    )
    parameters: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="The strategy-level parameters stored as JSONB. Contains configuration values such as thresholds, lookback windows, risk limits, etc.",
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolio.id"),
        nullable=False,
        comment="The identifier of the portfolio this strategy trades against",
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio")
    parameter_schema: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON Schema describing the strategy's parameters. Generated from the Strategy.Parameters Pydantic model at deploy time. The UI uses this to render a typed form instead of raw JSON.",
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the strategy is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the strategy",
    )

    # Relationships
    runs: Mapped[list["StrategyRun"]] = relationship(
        "StrategyRun", back_populates="strategy", order_by="StrategyRun.started_at.desc()"
    )
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="strategy")
    feeds: Mapped[list["StrategyFeed"]] = relationship(
        "StrategyFeed", order_by="StrategyFeed.order.asc()"
    )
    asset_scopes: Mapped[list["StrategyAssetScope"]] = relationship(
        "StrategyAssetScope",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyAssetScope.order.asc()",
    )
    states: Mapped[list["StrategyState"]] = relationship(
        "StrategyState",
        back_populates="strategy",
        order_by="StrategyState.timestamp.desc()",
    )

    def __repr__(self):
        return f"{Strategy.__name__}({self.id}, {self.name})"


class StrategyAssetScope(Base):
    __tablename__ = "strategy_asset_scope"
    __table_args__ = {
        "comment": "Defines which provider asset pairs a strategy monitors. The execution engine uses this to know which market data to fetch before any trade exists. Each row represents one provider-asset pair the strategy watches."
    }

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the strategy",
    )
    strategy: Mapped["Strategy"] = relationship(
        "Strategy", back_populates="asset_scopes", overlaps="asset_scopes"
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the from asset (base asset)",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the to asset (quote asset)",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    provider_asset_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider_asset_group.id"),
        nullable=True,
        comment="The identifier of the provider asset group, for group-based strategies like pairs trading or triangular arbitrage",
    )
    order: Mapped[int] = mapped_column(
        nullable=False,
        comment="The order of the asset pair within the strategy scope (1, 2, 3, etc.)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy asset scope record",
    )

    def __repr__(self):
        return f"{StrategyAssetScope.__name__}(strategy_id={self.strategy_id}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id})"


class StrategyRun(Base):
    __tablename__ = "strategy_run"
    __table_args__ = {
        "comment": "Represents an execution instance of a trading strategy. Tracks when the strategy ran, its status, and any errors encountered."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the strategy run",
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        nullable=False,
        comment="The identifier of the strategy that was executed",
    )
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="runs")
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="The status of the strategy run, e.g. PENDING, RUNNING, COMPLETED, FAILED",
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="The timestamp when the strategy run started",
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True,
        comment="The timestamp when the strategy run completed. Null if still running.",
    )
    error_message: Mapped[str | None] = mapped_column(
        String(5000),
        nullable=True,
        comment="The error message if the strategy run failed",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy run record",
    )

    # Relationships
    feed_run_links: Mapped[list["StrategyRunFeedRun"]] = relationship(
        "StrategyRunFeedRun",
        back_populates="strategy_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"{StrategyRun.__name__}(id={self.id}, strategy_id={self.strategy_id}, status={self.status})"


class StrategyState(Base):
    __tablename__ = "strategy_state"
    __table_args__ = {
        "comment": "Persists runtime state for a strategy between execution runs. The strategy engine loads the latest state at start() and persists it at stop(). Stores intermediate calculations, rolling statistics, or any state needed across executions."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the strategy state record",
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        nullable=False,
        comment="The identifier of the strategy",
    )
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="states")
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="The timestamp when this state was captured",
    )
    state_data: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
        comment="The runtime state data stored as JSONB. Contains intermediate calculations, rolling statistics, last processed timestamps, etc.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy state record",
    )

    def __repr__(self):
        return f"{StrategyState.__name__}(id={self.id}, strategy_id={self.strategy_id}, timestamp={self.timestamp})"
