import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.types import InstrumentType

if TYPE_CHECKING:
    from ascent.database.models.providers import Provider


class Exchange(NamedEntityMixin, Base):
    __tablename__ = "exchange"
    __table_args__ = {
        "comment": "Represents a trading exchange or execution venue. Users implement exchange classes via the BaseExchange interface and register them here with their configuration."
    }

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
