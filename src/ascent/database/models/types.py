import datetime
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class AssetType(Base):
    __tablename__ = "asset_type"
    __table_args__ = {"comment": "The type of asset, e.g. stock, bond, currency, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the asset type",
    )
    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        nullable=True,
        comment="The parent type in the type hierarchy. NULL means this is a root type.",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the asset type"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the asset type"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the asset type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the asset type",
    )

    parent_type: Mapped[Optional["AssetType"]] = relationship(
        remote_side=[id], back_populates="child_types"
    )
    child_types: Mapped[list["AssetType"]] = relationship(back_populates="parent_type")

    def __repr__(self):
        return f"{AssetType.__name__}({self.id}, {self.name})"


class ProviderType(Base):
    __tablename__ = "provider_type"
    __table_args__ = {"comment": "The type of provider, e.g. news, social media, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the provider type",
    )
    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider_type.id"),
        nullable=True,
        comment="The parent type in the type hierarchy. NULL means this is a root type.",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the provider type"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the provider type"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the provider type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the provider type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the provider type",
    )

    parent_type: Mapped[Optional["ProviderType"]] = relationship(
        remote_side=[id], back_populates="child_types"
    )
    child_types: Mapped[list["ProviderType"]] = relationship(back_populates="parent_type")

    def __repr__(self):
        return f"{ProviderType.__name__}({self.id}, {self.name})"


class ExchangeType(Base):
    __tablename__ = "exchange_type"
    __table_args__ = {"comment": "The type of exchange, e.g. spot, futures, paper, OTC"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the exchange type",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the exchange type"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the exchange type"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the exchange type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the exchange type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the exchange type",
    )

    def __repr__(self):
        return f"{ExchangeType.__name__}({self.id}, {self.name})"


class ContentType(Base):
    __tablename__ = "content_type"
    __table_args__ = {"comment": "The type of content, e.g. news, social media, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the content type",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the content type"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the content type"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the content type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the content type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the content type",
    )

    def __repr__(self):
        return f"{ContentType.__name__}({self.id}, {self.name})"


class SentimentType(Base):
    __tablename__ = "sentiment_type"
    __table_args__ = {
        "comment": "The type of sentiment in terms of the calculation method, e.g. PROVIDER, NLTK, VADER, etc. This is meant to store the sentiment type that is used to calculate the sentiment of a provider content."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the sentiment type",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the sentiment type"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the sentiment type"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the sentiment type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the sentiment type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the sentiment type",
    )

    def __repr__(self):
        return f"{SentimentType.__name__}({self.id}, {self.name})"


class TransactionType(Base):
    __tablename__ = "transaction_type"
    __table_args__ = {
        "comment": "The type of transaction, e.g. buy, sell, transfer, short, cover, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the transaction type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the transaction type, e.g. BUY, SELL, TRANSFER, SHORT, COVER, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the transaction type, e.g. Buy, Sell, Transfer, Short, Cover, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the transaction type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the transaction type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the transaction type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the transaction type",
    )

    def __repr__(self):
        return f"{TransactionType.__name__}({self.id}, {self.name})"


class TransactionStatusType(Base):
    __tablename__ = "transaction_status_type"
    __table_args__ = {
        "comment": "The type of transaction status, e.g. Pending, Open, Closed, Cancelled, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the transaction status type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the transaction status type, e.g. PENDING, OPEN, CLOSED, CANCELLED, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the transaction status type, e.g. Pending, Open, Closed, Cancelled, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the transaction status type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the transaction status type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the transaction status type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the transaction status type",
    )

    def __repr__(self):
        return f"{TransactionStatusType.__name__}({self.id}, {self.name})"


class FeedType(Base):
    __tablename__ = "feed_type"
    __table_args__ = {
        "comment": "The type of data feed, e.g. market data, sentiment, alternative data, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the feed type"
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the feed type, e.g. MARKET_DATA, SENTIMENT, ALTERNATIVE_DATA, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the feed type, e.g. Market Data, Sentiment, Alternative Data, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the feed type",
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the feed type is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the feed type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the feed type",
    )

    def __repr__(self):
        return f"{FeedType.__name__}({self.id}, {self.name})"


class StrategyType(Base):
    __tablename__ = "strategy_type"
    __table_args__ = {
        "comment": "The type of trading strategy, e.g. pairs trading, momentum, mean reversion, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the strategy type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the strategy type, e.g. PAIRS_TRADING, MOMENTUM, MEAN_REVERSION, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the strategy type, e.g. Pairs Trading, Momentum, Mean Reversion, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the strategy type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the strategy type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the strategy type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the strategy type",
    )

    def __repr__(self):
        return f"{StrategyType.__name__}({self.id}, {self.name})"


class TradeStatusType(Base):
    __tablename__ = "trade_status_type"
    __table_args__ = {
        "comment": "The type of trade status, e.g. Pending, Open, Partially Filled, Closed, Cancelled, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the trade status type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the trade status type, e.g. PENDING, OPEN, PARTIALLY_FILLED, CLOSED, CANCELLED, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the trade status type, e.g. Pending, Open, Partially Filled, Closed, Cancelled, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the trade status type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the trade status type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the trade status type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the trade status type",
    )

    def __repr__(self):
        return f"{TradeStatusType.__name__}({self.id}, {self.name})"


class OrderType(Base):
    __tablename__ = "order_type"
    __table_args__ = {"comment": "The type of order, e.g. Market, Limit, Stop, Stop Limit, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the order type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the order type, e.g. MARKET, LIMIT, STOP, STOP_LIMIT, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the order type, e.g. Market, Limit, Stop, Stop Limit, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the order type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the order type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the order type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the order type",
    )

    def __repr__(self):
        return f"{OrderType.__name__}({self.id}, {self.name})"


class OrderStatusType(Base):
    __tablename__ = "order_status_type"
    __table_args__ = {
        "comment": "The type of order status, e.g. Submitted, Accepted, Partially Filled, Filled, Cancelled, Rejected, etc."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="The unique identifier of the order status type",
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the order status type, e.g. SUBMITTED, ACCEPTED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The name of the order status type, e.g. Submitted, Accepted, Partially Filled, Filled, Cancelled, Rejected, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the order status type",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the order status type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the order status type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the order status type",
    )

    def __repr__(self):
        return f"{OrderStatusType.__name__}({self.id}, {self.name})"
