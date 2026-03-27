"""Feed-related database models."""

import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.providers import Provider
from ascent.database.models.types import FeedType


class Feed(Base):
    __tablename__ = "feed"
    __table_args__ = {
        "comment": (
            "Represents a registered data feed. Stores the feed configuration, "
            "importable function path, Pandera schema info, schedule, and Redis "
            "pub/sub channel. Each feed produces DataFrames that map to an EAV "
            "attribute table."
        )
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the feed"
    )
    feed_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed_type.id"),
        nullable=False,
        comment="The identifier of the feed type",
    )
    feed_type: Mapped["FeedType"] = relationship("FeedType")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="The name of the feed")
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the feed"
    )
    feed_ref: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment=(
            "The fully qualified importable Python path to the feed function, "
            "e.g. 'ascent.feeds.examples.market:market_data'"
        ),
    )
    parameters: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="The feed-level parameters stored as JSONB",
    )
    parameter_schema: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON Schema describing the feed's parameters, extracted from the function signature",
    )
    data_schema: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON Schema describing the feed's output DataFrame, extracted from the Pandera model",
    )
    output_table: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment=(
            "The DB table this feed's output maps to, "
            "e.g. 'provider_asset_attribute'. Derived from Pandera schema Config.name."
        ),
    )
    schedule: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "The schedule configuration as JSONB (interval, offset, anchor). "
            "Null for triggered feeds (depends_on)."
        ),
    )
    channel: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="The Redis pub/sub channel name for this feed, e.g. 'ascent.feed.{uuid}'",
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the feed is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the feed",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the feed",
    )

    # Relationships
    runs: Mapped[list["FeedRun"]] = relationship(
        "FeedRun", back_populates="feed", order_by="FeedRun.started_at.desc()"
    )
    partitions: Mapped[list["FeedPartition"]] = relationship(
        "FeedPartition", back_populates="feed", order_by="FeedPartition.partition_key.desc()"
    )
    dependencies: Mapped[list["FeedDependency"]] = relationship(
        "FeedDependency",
        back_populates="feed",
        foreign_keys="FeedDependency.feed_id",
    )
    asset_scopes: Mapped[list["FeedAssetScope"]] = relationship(
        "FeedAssetScope",
        back_populates="feed",
        cascade="all, delete-orphan",
        order_by="FeedAssetScope.order.asc()",
    )

    def __repr__(self):
        return f"Feed({self.id}, {self.name})"


class FeedDependency(Base):
    __tablename__ = "feed_dependency"
    __table_args__ = {
        "comment": (
            "Records DAG edges for triggered feeds. "
            "A triggered feed depends on one or more parent feeds."
        )
    }

    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the dependent (child) feed",
    )
    feed: Mapped["Feed"] = relationship(
        "Feed", back_populates="dependencies", foreign_keys=[feed_id]
    )
    depends_on_feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the parent feed",
    )
    depends_on_feed: Mapped["Feed"] = relationship("Feed", foreign_keys=[depends_on_feed_id])

    def __repr__(self):
        return f"FeedDependency(feed_id={self.feed_id}, depends_on={self.depends_on_feed_id})"


class StrategyFeed(Base):
    __tablename__ = "strategy_feed"
    __table_args__ = {
        "comment": (
            "Join table linking strategies to their feed dependencies. "
            "Determines which feeds trigger strategy evaluation."
        )
    }

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the strategy",
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the feed",
    )
    feed: Mapped["Feed"] = relationship("Feed")
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment=(
            "Whether this feed is required for triggering. "
            "Required feeds use AND logic (all must have data). "
            "Non-required feeds use OR logic (any triggers evaluation)."
        ),
    )
    order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="The order of the feed in the strategy's feed list",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy-feed link",
    )

    def __repr__(self):
        return f"StrategyFeed(strategy_id={self.strategy_id}, feed_id={self.feed_id})"


class FeedPartition(Base):
    __tablename__ = "feed_partition"
    __table_args__ = (
        UniqueConstraint("feed_id", "partition_key", name="uq_feed_partition_key"),
        {
            "comment": (
                "Represents a discrete time window (partition) for a feed. "
                "Partitions are defined by the feed's schedule and track whether "
                "the data for each window has been materialized."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the partition"
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        nullable=False,
        comment="The identifier of the feed this partition belongs to",
    )
    feed: Mapped["Feed"] = relationship("Feed", back_populates="partitions")
    partition_key: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="The boundary timestamp (logical time) identifying this partition",
    )
    window_start: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="Start of the time window (inclusive)",
    )
    window_end: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="End of the time window (exclusive)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        comment="The partition status: PENDING, MATERIALIZED, or FAILED",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the partition record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the partition record",
    )

    # Relationships
    runs: Mapped[list["FeedRun"]] = relationship(
        "FeedRun", back_populates="partition", order_by="FeedRun.started_at.desc()"
    )

    def __repr__(self):
        return f"FeedPartition(id={self.id}, feed_id={self.feed_id}, key={self.partition_key}, status={self.status})"


class FeedRun(Base):
    __tablename__ = "feed_run"
    __table_args__ = {
        "comment": (
            "Represents an execution instance of a data feed. "
            "Tracks when the feed ran, its status, and any errors encountered."
        )
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the feed run"
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        nullable=False,
        comment="The identifier of the feed that was executed",
    )
    feed: Mapped["Feed"] = relationship("Feed", back_populates="runs")
    partition_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("feed_partition.id"),
        nullable=True,
        comment="The partition this run belongs to. Null for legacy runs.",
    )
    partition: Mapped["FeedPartition | None"] = relationship("FeedPartition", back_populates="runs")
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="The status of the feed run, e.g. PENDING, RUNNING, COMPLETED, FAILED",
    )
    records_fetched: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="The number of records fetched in this run",
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="The timestamp when the feed run started",
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True,
        comment="The timestamp when the feed run completed. Null if still running.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="The error message if the feed run failed",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the feed run record",
    )

    def __repr__(self):
        return f"FeedRun(id={self.id}, feed_id={self.feed_id}, status={self.status})"


class FeedAssetScope(Base):
    __tablename__ = "feed_asset_scope"
    __table_args__ = {
        "comment": "Defines which provider asset pairs a feed covers. The execution engine uses this to know which market data a feed should fetch. Each row represents one provider-asset pair the feed handles."
    }

    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the feed",
    )
    feed: Mapped["Feed"] = relationship(
        "Feed", back_populates="asset_scopes", overlaps="asset_scopes"
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
        comment="Optional group this scope entry belongs to",
    )
    order: Mapped[int] = mapped_column(
        nullable=False,
        comment="The order of the asset pair within the feed scope (1, 2, 3, etc.)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the feed asset scope record",
    )

    def __repr__(self):
        return f"FeedAssetScope(feed_id={self.feed_id}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id})"
