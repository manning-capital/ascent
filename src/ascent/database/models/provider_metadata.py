import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base
from ascent.database.models.descriptors import Metadata
from ascent.database.models.providers import Provider


class ProviderMetadata(Base):
    __tablename__ = "provider_metadata"
    __table_args__ = {
        "comment": "Stores metadata attributes for providers as a temporal as-of table. "
        "Each metadata value is stored as a separate row with a timestamp, allowing "
        "historical tracking of metadata changes over time. New metadata attributes "
        "can be added without schema changes by referencing the Metadata descriptor table.",
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
    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("metadata.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the metadata type. References the Metadata table for metadata type definitions.",
    )
    metadata_type: Mapped["Metadata"] = relationship("Metadata")
    value: Mapped[str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
        comment="The primitive value of the metadata attribute for this provider. Allowed types: string, integer, float, boolean, date, time, datetime.",
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
        return f"{ProviderMetadata.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, metadata_id={self.metadata_id}, value={self.value})"
