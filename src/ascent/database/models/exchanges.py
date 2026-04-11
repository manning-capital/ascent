import datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.types import ExchangeType, InstrumentType

if TYPE_CHECKING:
    from ascent.database.models.composites import Composite
    from ascent.database.models.instruments import Instrument
    from ascent.database.models.providers import Provider


class Exchange(NamedEntityMixin, Base):
    __tablename__ = "exchange"
    __table_args__ = {
        "comment": "Represents a trading exchange or execution venue. Users implement exchange classes via the BaseExchange interface and register them here with their configuration."
    }

    exchange_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange_type.id"),
        nullable=False,
    )
    exchange_type: Mapped["ExchangeType"] = relationship("ExchangeType")
    instrument_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("instrument_type.id"),
        nullable=True,
    )
    instrument_type: Mapped[Optional["InstrumentType"]] = relationship("InstrumentType")
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
    )
    provider: Mapped[Optional["Provider"]] = relationship("Provider")
    implementation_class: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    instrument_scopes: Mapped[list["ExchangeInstrumentScope"]] = relationship(
        "ExchangeInstrumentScope",
        back_populates="exchange",
        cascade="all, delete-orphan",
        order_by="ExchangeInstrumentScope.order.asc()",
    )
    composite_scopes: Mapped[list["ExchangeCompositeScope"]] = relationship(
        "ExchangeCompositeScope",
        back_populates="exchange",
        cascade="all, delete-orphan",
        order_by="ExchangeCompositeScope.order.asc()",
    )


class ExchangeInstrumentScope(Base):
    __tablename__ = "exchange_instrument_scope"
    __table_args__ = {
        "comment": "Defines which instruments are available for trading on an exchange."
    }

    exchange_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange.id"),
        primary_key=True,
        nullable=False,
    )
    exchange: Mapped["Exchange"] = relationship(
        "Exchange", back_populates="instrument_scopes", overlaps="instrument_scopes"
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instrument.id"),
        primary_key=True,
        nullable=False,
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
    order: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class ExchangeCompositeScope(Base):
    __tablename__ = "exchange_composite_scope"
    __table_args__ = {
        "comment": "Defines which composites are available for trading on an exchange."
    }

    exchange_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange.id"),
        primary_key=True,
        nullable=False,
    )
    exchange: Mapped["Exchange"] = relationship(
        "Exchange", back_populates="composite_scopes", overlaps="composite_scopes"
    )
    composite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("composite.id"),
        primary_key=True,
        nullable=False,
    )
    composite: Mapped["Composite"] = relationship("Composite")
    order: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
