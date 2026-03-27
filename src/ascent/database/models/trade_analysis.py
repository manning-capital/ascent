import datetime
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.descriptors import Attribute, Period
from ascent.database.models.providers import Provider
from ascent.database.models.trades import Trade


class TradeCondition(Base):
    __tablename__ = "trade_condition"
    __table_args__ = {
        "comment": "Stores structured, queryable entry/exit conditions for a trade. Each condition defines a threshold on a market data attribute that triggers a trade action. Conditions are used by the UI to draw horizontal threshold lines on charts."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the trade condition",
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade.id"),
        nullable=False,
        comment="The identifier of the trade this condition belongs to",
    )
    trade: Mapped["Trade"] = relationship("Trade", back_populates="conditions")
    condition_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="The type of condition: ENTRY, EXIT, STOP_LOSS, TAKE_PROFIT",
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attribute.id"),
        nullable=False,
        comment="The identifier of the market data attribute this condition is based on, e.g. spread, z_score, rsi, close",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    operator: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="The comparison operator: ABOVE, BELOW, CROSSES_ABOVE, CROSSES_BELOW",
    )
    threshold_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The threshold value that triggers this condition. The UI draws a horizontal line at this level.",
    )
    is_met: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether this condition has been met/triggered",
    )
    met_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True,
        comment="The timestamp when this condition was met. Null if not yet met.",
    )
    # Context FKs — group-level or asset-level (one set populated per condition)
    provider_asset_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider_asset_group.id"),
        nullable=True,
        comment="The identifier of the provider asset group, for group-level attributes like spread. Mutually exclusive with provider/asset FKs.",
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
        comment="The identifier of the provider, for asset-level attributes",
    )
    provider: Mapped[Optional["Provider"]] = relationship("Provider")
    from_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the from asset (base asset), for asset-level attributes",
    )
    from_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the to asset (quote asset), for asset-level attributes",
    )
    to_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[to_asset_id])
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("period.id"),
        nullable=True,
        comment="The identifier of the period, for period-based attributes. Null for non-period attributes.",
    )
    period: Mapped[Optional["Period"]] = relationship("Period")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the trade condition record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the trade condition record",
    )

    def __repr__(self):
        return f"{TradeCondition.__name__}(id={self.id}, trade_id={self.trade_id}, condition_type={self.condition_type}, attribute_id={self.attribute_id}, operator={self.operator}, threshold_value={self.threshold_value})"


class TradeDataSeries(Base):
    __tablename__ = "trade_data_series"
    __table_args__ = {
        "comment": "Links a trade to relevant market data series for visualization. This is a pure reference table that tells the UI what data series are relevant to a trade. The UI decides how to display them. Actual time-series data lives in ProviderAssetAttribute or ProviderAssetGroupAttribute tables."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the trade data series",
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade.id"),
        nullable=False,
        comment="The identifier of the trade this data series is associated with",
    )
    trade: Mapped["Trade"] = relationship("Trade", back_populates="data_series")
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attribute.id"),
        nullable=False,
        comment="The identifier of the attribute to display, e.g. close, spread, z_score, rsi",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    label: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Optional human-readable label for the chart legend, e.g. 'ETH-BTC Spread', 'BTC/USD Close'",
    )
    data_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="The source table for the time-series data: ASSET_ATTRIBUTE, ASSET_PERIOD_ATTRIBUTE, GROUP_ATTRIBUTE, GROUP_PERIOD_ATTRIBUTE",
    )
    # Context FKs — group-level or asset-level
    provider_asset_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider_asset_group.id"),
        nullable=True,
        comment="The identifier of the provider asset group, for group-level data series",
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
        comment="The identifier of the provider, for asset-level data series",
    )
    provider: Mapped[Optional["Provider"]] = relationship("Provider")
    from_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the from asset (base asset), for asset-level data series",
    )
    from_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the to asset (quote asset), for asset-level data series",
    )
    to_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[to_asset_id])
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("period.id"),
        nullable=True,
        comment="The identifier of the period, for period-based attributes",
    )
    period: Mapped[Optional["Period"]] = relationship("Period")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the trade data series record",
    )

    def __repr__(self):
        return f"{TradeDataSeries.__name__}(id={self.id}, trade_id={self.trade_id}, attribute_id={self.attribute_id}, data_source={self.data_source})"


class TradeSnapshot(Base):
    __tablename__ = "trade_snapshot"
    __table_args__ = {
        "comment": "Captures signal/indicator values at key moments during a trade's lifecycle (entry, exit, checkpoints). Used for annotations and analysis. Follows the existing Attribute EAV pattern for consistency across model types."
    }

    trade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the trade",
    )
    trade: Mapped["Trade"] = relationship("Trade", back_populates="snapshots")
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attribute.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the attribute captured, e.g. spread, z_score, ou_mu, ou_sigma, rsi",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    snapshot_type: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        nullable=False,
        comment="The type of snapshot: ENTRY, EXIT, CHECKPOINT",
    )
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute at the time of the snapshot",
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        comment="The timestamp when this snapshot was taken",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the snapshot record",
    )

    def __repr__(self):
        return f"{TradeSnapshot.__name__}(trade_id={self.trade_id}, attribute_id={self.attribute_id}, snapshot_type={self.snapshot_type}, attribute_value={self.attribute_value})"
