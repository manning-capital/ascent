import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.descriptors import Attribute, Period
from ascent.database.models.instruments import Instrument
from ascent.database.models.types import CompositeType


class Composite(NamedEntityMixin, Base):
    __tablename__ = "composite"
    __table_args__ = {
        "comment": "Represents a named grouping of instruments for analysis and trading, e.g. a pairs spread, basket, or index."
    }

    composite_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite_type.id"),
        nullable=False,
        comment="The identifier of the composite type",
    )
    composite_type: Mapped["CompositeType"] = relationship("CompositeType")
    members: Mapped[list["CompositeMember"]] = relationship(
        "CompositeMember",
        cascade="all, delete-orphan",
        order_by="CompositeMember.order.asc()",
    )

    def __repr__(self):
        return f"{Composite.__name__}(id={self.id}, name={self.name})"


class CompositeMember(Base):
    __tablename__ = "composite_member"
    __table_args__ = {
        "comment": "Join table linking composites to their constituent instruments with ordering."
    }

    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the composite",
    )
    composite: Mapped["Composite"] = relationship("Composite", overlaps="members")
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the instrument",
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    order: Mapped[int] = mapped_column(
        nullable=False,
        comment="The order of the instrument within the composite (1, 2, 3, etc.).",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the composite member",
    )

    def __repr__(self):
        return f"{CompositeMember.__name__}(composite_id={self.composite_id}, instrument_id={self.instrument_id}, order={self.order})"


class CompositeAttribute(Base):
    __tablename__ = "composite_attribute"
    __table_args__ = {
        "comment": "Stores attributes for composites without time periods, e.g. spread value, z-score.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the composite attributes",
    )
    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the composite",
    )
    composite: Mapped["Composite"] = relationship("Composite")
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
        comment="The value of the attribute for the composite at the given timestamp",
    )

    def __repr__(self):
        return f"{CompositeAttribute.__name__}(timestamp={self.timestamp}, composite_id={self.composite_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class CompositePeriodAttribute(Base):
    __tablename__ = "composite_period_attribute"
    __table_args__ = {
        "comment": "Stores aggregated statistical calculations for composites across multiple time periods.",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the composite attributes",
    )
    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the composite",
    )
    composite: Mapped["Composite"] = relationship("Composite")
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
        comment="The value of the attribute for the composite at the given timestamp and period",
    )

    def __repr__(self):
        return f"{CompositePeriodAttribute.__name__}(timestamp={self.timestamp}, composite_id={self.composite_id}, period_id={self.period_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"
