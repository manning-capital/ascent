import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, func, mapped_column, relationship

from summit.database.models.assets import Asset
from summit.database.models.base import Base
from summit.database.models.descriptors import Attribute, Metadata, Period
from summit.database.models.providers import Provider


class ProviderAssetAttribute(Base):
    __tablename__ = "provider_asset_attribute"
    __table_args__ = {
        "comment": "Stores market data attributes for provider asset markets. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new market data attributes to be added without schema changes.",
        "postgresql_partition_by": "HASH (attribute_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset market",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the from asset. This is also called the base asset.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the to asset. This is also called the quote asset.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider asset market at the given timestamp",
    )

    def __repr__(self):
        return f"{ProviderAssetAttribute.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class ProviderAssetPeriodAttribute(Base):
    __tablename__ = "provider_asset_period_attribute"
    __table_args__ = {
        "comment": "Stores market data attributes for provider asset markets with time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new market data attributes to be added without schema changes. Periods are defined in the Period table for reusability.",
        "postgresql_partition_by": "HASH (attribute_id, period_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset market",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the from asset. This is also called the base asset.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the to asset. This is also called the quote asset.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    period_id: Mapped[int] = mapped_column(
        ForeignKey("period.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the period used for the calculation",
    )
    period: Mapped["Period"] = relationship("Period")
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider asset market at the given timestamp and period",
    )

    def __repr__(self):
        return f"{ProviderAssetPeriodAttribute.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, period_id={self.period_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class ProviderAssetMetadata(Base):
    __tablename__ = "provider_asset_metadata"
    __table_args__ = {
        "comment": "Stores text/metadata attributes for provider assets (e.g., symbols like 'BTC' vs 'XBT', exchange codes, provider-specific identifiers). Replaces the original ProviderAsset table's asset_code field with a flexible attribute-based design. Each metadata value is stored as a separate row, allowing new metadata attributes to be added without schema changes. Similar to ProviderAssetAttribute but for text values instead of numerical values. Tracks metadata history through time-series snapshots.",
        "postgresql_partition_by": "HASH (metadata_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        comment="The timestamp when this metadata snapshot is valid. Part of the primary key to enable time-series metadata tracking and historical reconciliation.",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the asset",
    )
    asset: Mapped["Asset"] = relationship("Asset")
    metadata_id: Mapped[int] = mapped_column(
        ForeignKey("metadata.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the metadata type (e.g., 'symbol', 'exchange_code', 'provider_ticker'). References the Metadata table for metadata type definitions.",
    )
    metadata: Mapped["Metadata"] = relationship("Metadata")
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
        comment="The JSON value of the metadata attribute for this provider asset. Can store text, numbers, booleans, objects, or arrays. For example, 'BTC' or 'XBT' for Bitcoin symbol, or more complex structured data.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the metadata record",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the metadata record",
    )

    def __repr__(self):
        return f"{ProviderAssetMetadata.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, asset_id={self.asset_id}, metadata_id={self.metadata_id}, value={self.value})"
