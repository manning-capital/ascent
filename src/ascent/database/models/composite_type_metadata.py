import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class CompositeTypeMetadata(Base):
    __tablename__ = "composite_type_metadata"
    __table_args__ = {
        "comment": "Junction table linking composite types to their required/optional metadata fields. Defines which metadata fields are relevant for each composite type and whether they are required."
    }

    composite_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite_type.id"),
        primary_key=True,
        comment="The composite type this metadata requirement belongs to",
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        primary_key=True,
        comment="The metadata type that is required/optional for this composite type",
    )
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this metadata field is required for composites of this type",
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

    composite_type = relationship("CompositeType", lazy="joined")
    metadata_type = relationship("Metadata", lazy="joined")

    def __repr__(self):
        return f"CompositeTypeMetadata(composite_type={self.composite_type_id}, metadata={self.metadata_id})"
