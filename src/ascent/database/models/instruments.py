import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.descriptors import Attribute, Period
from ascent.database.models.providers import Provider
from ascent.database.models.types import InstrumentType


class Instrument(NamedEntityMixin, Base):
    __tablename__ = "instrument"
    __table_args__ = {
        "comment": "Represents an atomic tradeable instrument — exactly one provider and one asset pair (e.g. Kraken BTC/USD Spot)."
    }

    instrument_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument_type.id"),
        nullable=False,
        comment="The identifier of the instrument type",
    )
    instrument_type: Mapped["InstrumentType"] = relationship("InstrumentType")
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=False,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the from asset (base asset)",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the to asset (quote asset)",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])

    def __repr__(self):
        return f"{Instrument.__name__}(id={self.id}, name={self.name})"


class InstrumentAttribute(Base):
    # TODO: Re-add partitioning when needed. Previously partitioned by HASH (attribute_id)
    __tablename__ = "instrument_attribute"
    __table_args__ = {
        "comment": "Stores attributes for instruments without time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new attributes to be added without schema changes.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the instrument attributes",
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the instrument",
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the instrument at the given timestamp",
    )

    def __repr__(self):
        return f"{InstrumentAttribute.__name__}(timestamp={self.timestamp}, instrument_id={self.instrument_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class InstrumentPeriodAttribute(Base):
    # TODO: Re-add partitioning when needed. Previously partitioned by HASH (attribute_id, period_id)
    __tablename__ = "instrument_period_attribute"
    __table_args__ = {
        "comment": "Stores aggregated statistical calculations for instruments across multiple time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new attributes to be added without schema changes. Periods are defined in the Period table for reusability.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the instrument attributes",
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the instrument",
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("period.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the period used for the calculation",
    )
    period: Mapped["Period"] = relationship("Period")
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the instrument at the given timestamp and period",
    )

    def __repr__(self):
        return f"{InstrumentPeriodAttribute.__name__}(timestamp={self.timestamp}, instrument_id={self.instrument_id}, period_id={self.period_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"
