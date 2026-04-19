import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.composites import Composite
from ascent.database.models.instruments import Instrument
from ascent.database.models.portfolio import Portfolio

if TYPE_CHECKING:
    from ascent.database.models.exchanges import Exchange
    from ascent.database.models.feeds import StrategyFeed
    from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun
    from ascent.database.models.trades import Trade


class Strategy(NamedEntityMixin, Base):
    __tablename__ = "strategy"
    __table_args__ = {
        "comment": "Represents a registered trading strategy. Stores the strategy configuration, importable class path, and JSONB parameters."
    }

    strategy_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    parameters: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolio.id"),
        nullable=False,
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio")
    parameter_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_paused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    runs: Mapped[list["StrategyRun"]] = relationship(
        "StrategyRun", back_populates="strategy", order_by="StrategyRun.started_at.desc()"
    )
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="strategy")
    feeds: Mapped[list["StrategyFeed"]] = relationship(
        "StrategyFeed", order_by="StrategyFeed.order.asc()"
    )
    instrument_scopes: Mapped[list["StrategyInstrumentScope"]] = relationship(
        "StrategyInstrumentScope",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyInstrumentScope.order.asc()",
    )
    composite_scopes: Mapped[list["StrategyCompositeScope"]] = relationship(
        "StrategyCompositeScope",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyCompositeScope.order.asc()",
    )
    exchange_scopes: Mapped[list["StrategyExchange"]] = relationship(
        "StrategyExchange",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyExchange.order.asc()",
    )
    states: Mapped[list["StrategyState"]] = relationship(
        "StrategyState",
        back_populates="strategy",
        order_by="StrategyState.timestamp.desc()",
    )


class StrategyInstrumentScope(Base):
    __tablename__ = "strategy_instrument_scope"
    __table_args__ = {"comment": "Defines which instruments a strategy monitors."}

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship(
        "Strategy", back_populates="instrument_scopes", overlaps="instrument_scopes"
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        primary_key=True,
        nullable=False,
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class StrategyCompositeScope(Base):
    __tablename__ = "strategy_composite_scope"
    __table_args__ = {"comment": "Defines which composites a strategy monitors."}

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship(
        "Strategy", back_populates="composite_scopes", overlaps="composite_scopes"
    )
    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        primary_key=True,
        nullable=False,
    )
    composite: Mapped["Composite"] = relationship("Composite")
    order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class StrategyExchange(Base):
    __tablename__ = "strategy_exchange"
    __table_args__ = {
        "comment": "Defines which exchanges a strategy can use for order execution. Enables routing of instruments to the correct exchange when trading composites that span multiple providers."
    }

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship(
        "Strategy", back_populates="exchange_scopes", overlaps="exchange_scopes"
    )
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange.id"),
        primary_key=True,
        nullable=False,
    )
    exchange: Mapped["Exchange"] = relationship("Exchange")
    order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class StrategyRun(Base):
    __tablename__ = "strategy_run"
    __table_args__ = {"comment": "Represents an execution instance of a trading strategy."}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="runs")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    feed_run_links: Mapped[list["StrategyRunFeedRun"]] = relationship(
        "StrategyRunFeedRun",
        back_populates="strategy_run",
        cascade="all, delete-orphan",
    )


class StrategyState(Base):
    __tablename__ = "strategy_state"
    __table_args__ = {"comment": "Persists runtime state for a strategy between execution runs."}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="states")
    timestamp: Mapped[datetime.datetime] = mapped_column(nullable=False)
    state_data: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
