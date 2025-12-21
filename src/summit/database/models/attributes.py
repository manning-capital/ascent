import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, func, mapped_column

from summit.database.models.base import Base


class Attribute(Base):
    __tablename__ = "attribute"
    __table_args__ = {
        "comment": "Stores attribute definitions for provider asset groups. This table allows extending attributes without changing the database schema, as new attributes can be added as rows rather than columns."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the attribute"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the attribute, e.g. cointegration_p_value, ou_mu, linear_fit_alpha, etc.",
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the attribute, explaining what it represents and how it is calculated",
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the attribute is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the attribute",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the attribute",
    )

    def __repr__(self):
        return f"{Attribute.__name__}({self.id}, {self.name})"


class Period(Base):
    __tablename__ = "period"
    __table_args__ = {
        "comment": "Defines time periods that can be reused across different tables. Allows dynamic period definitions without schema changes."
    }

    id: Mapped[int] = mapped_column(primary_key=True, comment="The unique identifier of the period")
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the period, e.g. '1 hour', '1 day', '1 week', etc.",
        unique=True,
    )
    duration_nanoseconds: Mapped[int] = mapped_column(
        nullable=False,
        comment="The duration of the period in nanoseconds",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the period, explaining its purpose and usage",
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the period is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the period",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the period",
    )

    def __repr__(self):
        return f"{Period.__name__}({self.id}, {self.name})"


class Metadata(Base):
    __tablename__ = "metadata"
    __table_args__ = {
        "comment": "Stores metadata type definitions for provider assets (e.g., symbol, exchange_code, provider_ticker). This table allows extending metadata types without changing the database schema, as new metadata types can be added as rows rather than columns. Separate from Attribute table to distinguish between numerical attributes and text metadata."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the metadata type"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the metadata type, e.g. symbol, exchange_code, provider_ticker, etc.",
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the metadata type, explaining what it represents and how it is used",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the metadata type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the metadata type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the metadata type",
    )

    def __repr__(self):
        return f"{Metadata.__name__}({self.id}, {self.name})"
