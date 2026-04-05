from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ascent.database.models.base import Base, NamedEntityMixin


class Attribute(NamedEntityMixin, Base):
    __tablename__ = "attribute"
    __table_args__ = {
        "comment": "Stores attribute type definitions for numerical/temporal floating point values. Attributes represent the numerical state of an item at a point in time (e.g., close price, volume, cointegration_p_value, ou_mu, linear_fit_alpha)."
    }


class Period(NamedEntityMixin, Base):
    __tablename__ = "period"
    __table_args__ = {
        "comment": "Defines time periods that extend attributes to represent lookback periods. When an attribute is used with a period, it signifies that the attribute applies to the timestamp or a lookback period (e.g., 1 hour, 1 day, 1 week)."
    }

    duration_nanoseconds: Mapped[int] = mapped_column(nullable=False)


class Metadata(NamedEntityMixin, Base):
    __tablename__ = "metadata"
    __table_args__ = {
        "comment": "Stores metadata type definitions for categorical and structured data (e.g., symbol, exchange_code, provider_ticker). Metadata categorizes items as-of a particular time and represents non-numerical characteristics stored as JSON values."
    }

    value_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="string",
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Type-specific configuration (e.g. enum options, reference target table).",
    )
