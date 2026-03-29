import datetime
import uuid

from sqlalchemy import String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ascent.database.models.base import Base


class Attribute(Base):
    __tablename__ = "attribute"
    __table_args__ = {
        "comment": "Stores attribute type definitions for numerical/temporal floating point values. Attributes represent the numerical state of an item at a point in time (e.g., close price, volume, cointegration_p_value, ou_mu, linear_fit_alpha). This table allows extending attributes without changing the database schema, as new attributes can be added as rows rather than columns."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the attribute"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the attribute, e.g. cointegration_p_value, ou_mu, linear_fit_alpha, close_price, volume, etc. These represent numerical state values at a point in time.",
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the attribute, explaining what numerical state it represents and how it is calculated. Attributes are temporal floating point values representing the state of an item at a specific time.",
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
        "comment": "Defines time periods that extend attributes to represent lookback periods. When an attribute is used with a period, it signifies that the attribute applies to the timestamp or a lookback period (e.g., 1 hour, 1 day, 1 week). Allows dynamic period definitions without schema changes."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the period"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the period following pandas/datetime timedelta conventions, e.g. '1H' (1 hour), '1D' (1 day), '1W' (1 week), '1M' (1 month), '1Y' (1 year). When used with an attribute, this represents the lookback period for that attribute calculation.",
        unique=True,
    )
    duration_nanoseconds: Mapped[int] = mapped_column(
        nullable=False,
        comment="The duration of the period in nanoseconds. Defines the lookback window when the period is used with an attribute.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the period, explaining its purpose and usage. Periods extend attributes to apply them over a lookback window rather than just at a single timestamp.",
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
        "comment": "Stores metadata type definitions for categorical and structured data (e.g., symbol, exchange_code, provider_ticker). Metadata categorizes items as-of a particular time and represents non-numerical characteristics stored as JSON values. Values can be text, numbers, booleans, objects, or arrays, allowing for dynamic and structured data. This table allows extending metadata types without changing the database schema, as new metadata types can be added as rows rather than columns. Separate from Attribute table to distinguish between numerical temporal state values (attributes) and categorical/structured classification data (metadata)."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the metadata type",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the metadata type, e.g. symbol, exchange_code, provider_ticker, etc. These represent categorical classifications or structured data as-of a particular time, stored as JSON values.",
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable display name shown in the UI (e.g. 'Market Cap').",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the metadata type, explaining what categorical classification or structured data it represents and how it is used. Metadata values are stored as JSON (text, numbers, booleans, objects, or arrays) that categorizes or describes items as-of a particular time.",
    )
    value_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="string",
        comment="The data type for this metadata's value. One of: string, integer, float, boolean, date, time, datetime. Controls how the form renders in the UI.",
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
