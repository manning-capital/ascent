import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class AssetTypeProviderAssetMetadata(Base):
    __tablename__ = "asset_type_provider_asset_metadata"
    __table_args__ = {
        "comment": "Defines which metadata fields are required/optional for provider-asset "
        "mappings of a given asset type. For example, a Cryptocurrency type may require "
        "a 'provider_ticker' field so each exchange's symbol for the asset is captured."
    }

    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        primary_key=True,
        comment="The asset type this provider-asset metadata requirement belongs to",
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        primary_key=True,
        comment="The metadata type that is required/optional for provider-asset links of this asset type",
    )
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this metadata field is required for provider-asset mappings",
    )
    display_order: Mapped[int] = mapped_column(
        default=0,
        comment="The display order of this field in the provider-asset metadata form",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation",
    )

    asset_type = relationship("AssetType", lazy="joined")
    metadata_type = relationship("Metadata", lazy="joined")

    def __repr__(self):
        return f"AssetTypeProviderAssetMetadata(asset_type={self.asset_type_id}, metadata={self.metadata_id})"
