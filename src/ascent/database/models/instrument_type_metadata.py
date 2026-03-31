import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class InstrumentTypeMetadata(Base):
    __tablename__ = "instrument_type_metadata"
    __table_args__ = {
        "comment": "Junction table linking instrument types to their required/optional metadata fields. Defines which metadata fields are relevant for each instrument type and whether they are required."
    }

    instrument_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument_type.id"),
        primary_key=True,
        comment="The instrument type this metadata requirement belongs to",
    )
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        primary_key=True,
        comment="The metadata type that is required/optional for this instrument type",
    )
    is_required: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this metadata field is required for instruments of this type",
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

    instrument_type = relationship("InstrumentType", lazy="joined")
    metadata_type = relationship("Metadata", lazy="joined")

    def __repr__(self):
        return f"InstrumentTypeMetadata(instrument_type={self.instrument_type_id}, metadata={self.metadata_id})"
