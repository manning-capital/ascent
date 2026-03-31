import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base
from ascent.database.models.descriptors import Metadata
from ascent.database.models.instruments import Instrument


class InstrumentMetadata(Base):
    __tablename__ = "instrument_metadata"
    __table_args__ = {
        "comment": "Stores metadata attributes for instruments as a temporal as-of table. "
        "Each metadata value is stored as a separate row with a timestamp, allowing "
        "historical tracking of metadata changes over time.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        comment="The timestamp when this metadata snapshot is valid.",
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the instrument",
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the metadata type.",
    )
    metadata_type: Mapped["Metadata"] = relationship("Metadata")
    value: Mapped[str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
        comment="The primitive value of the metadata attribute for this instrument.",
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
        return f"{InstrumentMetadata.__name__}(timestamp={self.timestamp}, instrument_id={self.instrument_id}, metadata_id={self.metadata_id}, value={self.value})"
