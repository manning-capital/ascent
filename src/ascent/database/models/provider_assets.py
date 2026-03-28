import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.descriptors import Metadata
from ascent.database.models.providers import Provider


class ProviderAssetMetadata(Base):
    # TODO: Re-add partitioning when needed. Previously partitioned by HASH (metadata_id)
    __tablename__ = "provider_asset_metadata"
    __table_args__ = {
        "comment": "Stores text/metadata attributes for provider assets (e.g., symbols like 'BTC' vs 'XBT', exchange codes, provider-specific identifiers). Uses a flexible attribute-based design where each metadata value is stored as a separate row, allowing new metadata attributes to be added without schema changes. Tracks metadata history through time-series snapshots.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        comment="The timestamp when this metadata snapshot is valid. Part of the primary key to enable time-series metadata tracking and historical reconciliation.",
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the asset",
    )
    asset: Mapped["Asset"] = relationship("Asset")
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the metadata type (e.g., 'symbol', 'exchange_code', 'provider_ticker'). References the Metadata table for metadata type definitions.",
    )
    metadata_type: Mapped["Metadata"] = relationship("Metadata")
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
