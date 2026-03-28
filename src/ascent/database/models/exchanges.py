import datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base
from ascent.database.models.types import ExchangeType

if TYPE_CHECKING:
    from ascent.database.models.providers import Provider


class Exchange(Base):
    __tablename__ = "exchange"
    __table_args__ = {
        "comment": "Represents a trading exchange or execution venue. Users implement exchange classes via the BaseExchange interface and register them here with their configuration."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the exchange",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the exchange, e.g. Kraken, Binance, Paper Trading",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="A description of the exchange",
    )
    exchange_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange_type.id"),
        nullable=False,
        comment="The identifier of the exchange type, e.g. Spot, Futures, Paper, OTC",
    )
    exchange_type: Mapped["ExchangeType"] = relationship("ExchangeType")
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
        comment="The optional identifier of the backing data provider. An exchange may be backed by a provider for market data.",
    )
    provider: Mapped[Optional["Provider"]] = relationship("Provider")
    implementation_class: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="The dotted Python path to the BaseExchange implementation class, e.g. ascent.exchanges.paper.PaperExchange",
    )
    config: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Exchange-specific configuration stored as JSONB, e.g. API keys, endpoints, custom settings",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether the exchange is active and available for order submission",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the exchange record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the exchange record",
    )

    def __repr__(self):
        return f"{Exchange.__name__}(id={self.id}, name={self.name})"
