import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin


class AssetType(NamedEntityMixin, Base):
    __tablename__ = "asset_type"
    __table_args__ = {"comment": "The type of asset, e.g. stock, bond, currency, etc."}

    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        nullable=True,
    )

    parent_type: Mapped[Optional["AssetType"]] = relationship(
        remote_side="AssetType.id", back_populates="child_types"
    )
    child_types: Mapped[list["AssetType"]] = relationship(back_populates="parent_type")


class ProviderType(NamedEntityMixin, Base):
    __tablename__ = "provider_type"
    __table_args__ = {"comment": "The type of provider, e.g. news, social media, etc."}

    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider_type.id"),
        nullable=True,
    )

    parent_type: Mapped[Optional["ProviderType"]] = relationship(
        remote_side="ProviderType.id", back_populates="child_types"
    )
    child_types: Mapped[list["ProviderType"]] = relationship(back_populates="parent_type")


class ContentType(NamedEntityMixin, Base):
    __tablename__ = "content_type"
    __table_args__ = {"comment": "The type of content, e.g. news, social media, etc."}


class SentimentType(NamedEntityMixin, Base):
    __tablename__ = "sentiment_type"
    __table_args__ = {
        "comment": "The type of sentiment calculation method, e.g. PROVIDER, NLTK, VADER, etc."
    }


class TransactionType(NamedEntityMixin, Base):
    __tablename__ = "transaction_type"
    __table_args__ = {
        "comment": "The type of transaction, e.g. buy, sell, transfer, short, cover, etc."
    }


class TransactionStatusType(NamedEntityMixin, Base):
    __tablename__ = "transaction_status_type"
    __table_args__ = {
        "comment": "The type of transaction status, e.g. pending, open, closed, cancelled, etc."
    }


class TradeStatusType(NamedEntityMixin, Base):
    __tablename__ = "trade_status_type"
    __table_args__ = {
        "comment": "The type of trade status, e.g. pending, open, closed, cancelled, etc."
    }


class OrderType(NamedEntityMixin, Base):
    __tablename__ = "order_type"
    __table_args__ = {"comment": "The type of order, e.g. market, limit, stop, stop_limit, etc."}


class InstrumentType(NamedEntityMixin, Base):
    __tablename__ = "instrument_type"
    __table_args__ = {
        "comment": "The type of atomic instrument, e.g. security, perpetual, future, option, etc."
    }

    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("instrument_type.id"),
        nullable=True,
    )

    parent_type: Mapped[Optional["InstrumentType"]] = relationship(
        remote_side="InstrumentType.id", back_populates="child_types"
    )
    child_types: Mapped[list["InstrumentType"]] = relationship(back_populates="parent_type")


class CompositeType(NamedEntityMixin, Base):
    __tablename__ = "composite_type"
    __table_args__ = {
        "comment": "The type of composite instrument grouping, e.g. spread, basket, index, etc."
    }

    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("composite_type.id"),
        nullable=True,
    )
    min_members: Mapped[int] = mapped_column(
        default=2,
        comment="Minimum number of instruments allowed in composites of this type",
    )
    max_members: Mapped[int] = mapped_column(
        default=2,
        comment="Maximum number of instruments allowed in composites of this type",
    )

    parent_type: Mapped[Optional["CompositeType"]] = relationship(
        remote_side="CompositeType.id", back_populates="child_types"
    )
    child_types: Mapped[list["CompositeType"]] = relationship(back_populates="parent_type")


class OrderStatusType(NamedEntityMixin, Base):
    __tablename__ = "order_status_type"
    __table_args__ = {
        "comment": "The type of order status, e.g. submitted, accepted, filled, cancelled, rejected, etc."
    }
