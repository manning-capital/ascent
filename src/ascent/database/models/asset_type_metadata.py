import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class AssetTypeMetadata(Base):
    __tablename__ = "asset_type_metadata"
    __table_args__ = {
        "comment": "Junction table linking asset types to their required/optional metadata fields. Defines which metadata fields are relevant for each asset type and whether they are required."
    }

    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        primary_key=True,
        comment="The asset type this metadata requirement belongs to",
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        primary_key=True,
        comment="The metadata type that is required/optional for this asset type",
    )
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this metadata field is required for assets of this type",
    )
    display_order: Mapped[int] = mapped_column(
        default=0,
        comment="The display order of this field in the metadata form",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation",
    )

    asset_type = relationship("AssetType", lazy="joined")
    metadata_type = relationship("Metadata", lazy="joined")

    def __repr__(self):
        return f"AssetTypeMetadata(asset_type={self.asset_type_id}, metadata={self.metadata_id})"
