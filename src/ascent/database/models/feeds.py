"""Feed-related database models."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.instruments import Instrument
from ascent.database.models.types import CompositeType, InstrumentType

if TYPE_CHECKING:
    from ascent.database.models.composites import Composite
    from ascent.database.models.providers import Provider


class Feed(NamedEntityMixin, Base):
    __tablename__ = "feed"
    __table_args__ = (
        CheckConstraint(
            "(instrument_type_id IS NOT NULL AND composite_type_id IS NULL) OR "
            "(instrument_type_id IS NULL AND composite_type_id IS NOT NULL)",
            name="ck_feed_scope_xor",
        ),
        {
            "comment": (
                "Represents a registered data feed. Stores the feed configuration, "
                "importable function path, Pandera schema info, schedule, and Redis "
                "pub/sub channel."
            )
        },
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=False,
    )
    provider: Mapped[Provider] = relationship("Provider")
    instrument_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("instrument_type.id"),
        nullable=True,
    )
    instrument_type: Mapped[InstrumentType | None] = relationship("InstrumentType")
    composite_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("composite_type.id"),
        nullable=True,
    )
    composite_type: Mapped[CompositeType | None] = relationship("CompositeType")
    feed_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    parameters: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    parameter_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    data_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_table: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    channel: Mapped[str] = mapped_column(String(200), nullable=False)

    # Relationships
    runs: Mapped[list[FeedRun]] = relationship(
        "FeedRun", back_populates="feed", order_by="FeedRun.started_at.desc()"
    )
    partitions: Mapped[list[FeedPartition]] = relationship(
        "FeedPartition", back_populates="feed", order_by="FeedPartition.partition_key.desc()"
    )
    dependencies: Mapped[list[FeedDependency]] = relationship(
        "FeedDependency",
        back_populates="feed",
        foreign_keys="FeedDependency.feed_id",
    )
    instrument_scopes: Mapped[list[FeedInstrumentScope]] = relationship(
        "FeedInstrumentScope",
        back_populates="feed",
        cascade="all, delete-orphan",
        order_by="FeedInstrumentScope.order.asc()",
    )
    composite_scopes: Mapped[list[FeedCompositeScope]] = relationship(
        "FeedCompositeScope",
        back_populates="feed",
        cascade="all, delete-orphan",
        order_by="FeedCompositeScope.order.asc()",
    )


class FeedDependency(Base):
    __tablename__ = "feed_dependency"
    __table_args__ = {"comment": "Records DAG edges for triggered feeds."}

    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
    )
    feed: Mapped[Feed] = relationship("Feed", back_populates="dependencies", foreign_keys=[feed_id])
    depends_on_feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
    )
    depends_on_feed: Mapped[Feed] = relationship("Feed", foreign_keys=[depends_on_feed_id])


class StrategyFeed(Base):
    __tablename__ = "strategy_feed"
    __table_args__ = {"comment": "Join table linking strategies to their feed dependencies."}

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
    )
    feed: Mapped[Feed] = relationship("Feed")
    is_required: Mapped[bool] = mapped_column(default=True)
    order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class FeedPartition(Base):
    __tablename__ = "feed_partition"
    __table_args__ = (
        UniqueConstraint("feed_id", "partition_key", name="uq_feed_partition_key"),
        {"comment": "Represents a discrete time window (partition) for a feed."},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        nullable=False,
    )
    feed: Mapped[Feed] = relationship("Feed", back_populates="partitions")
    partition_key: Mapped[datetime.datetime] = mapped_column(nullable=False)
    window_start: Mapped[datetime.datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime.datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
    )
    runs: Mapped[list[FeedRun]] = relationship(
        "FeedRun", back_populates="partition", order_by="FeedRun.started_at.desc()"
    )


class FeedRun(Base):
    __tablename__ = "feed_run"
    __table_args__ = {"comment": "Represents an execution instance of a data feed."}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        nullable=False,
    )
    feed: Mapped[Feed] = relationship("Feed", back_populates="runs")
    partition_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("feed_partition.id"),
        nullable=True,
    )
    partition: Mapped[FeedPartition | None] = relationship("FeedPartition", back_populates="runs")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    records_fetched: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class FeedInstrumentScope(Base):
    __tablename__ = "feed_instrument_scope"
    __table_args__ = {"comment": "Defines which instruments a feed covers."}

    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
    )
    feed: Mapped[Feed] = relationship(
        "Feed", back_populates="instrument_scopes", overlaps="instrument_scopes"
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        primary_key=True,
        nullable=False,
    )
    instrument: Mapped[Instrument] = relationship("Instrument")
    order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class FeedCompositeScope(Base):
    __tablename__ = "feed_composite_scope"
    __table_args__ = {"comment": "Defines which composites a feed covers."}

    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
    )
    feed: Mapped[Feed] = relationship(
        "Feed", back_populates="composite_scopes", overlaps="composite_scopes"
    )
    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        primary_key=True,
        nullable=False,
    )
    composite: Mapped[Composite] = relationship("Composite")
    order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
