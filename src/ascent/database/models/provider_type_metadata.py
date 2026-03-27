import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class ProviderTypeMetadata(Base):
    __tablename__ = "provider_type_metadata"
    __table_args__ = {
        "comment": "Junction table linking provider types to their required/optional metadata fields. Defines which metadata fields are relevant for each provider type and whether they are required."
    }

    provider_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider_type.id"),
        primary_key=True,
        comment="The provider type this metadata requirement belongs to",
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        primary_key=True,
        comment="The metadata type that is required/optional for this provider type",
    )
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this metadata field is required for providers of this type",
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

    provider_type = relationship("ProviderType", lazy="joined")
    metadata_type = relationship("Metadata", lazy="joined")

    def __repr__(self):
        return f"ProviderTypeMetadata(provider_type={self.provider_type_id}, metadata={self.metadata_id})"
