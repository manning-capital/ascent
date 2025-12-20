import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, func, mapped_column

from summit.database.models.base import Base


class AssetType(Base):
    __tablename__ = "asset_type"
    __table_args__ = {"comment": "The type of asset, e.g. stock, bond, currency, etc."}

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the asset type"
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

    def __repr__(self):
        return f"{AssetType.__name__}({self.id}, {self.name})"


class ProviderType(Base):
    __tablename__ = "provider_type"
    __table_args__ = {"comment": "The type of provider, e.g. news, social media, etc."}

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the provider type"
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

    def __repr__(self):
        return f"{ProviderType.__name__}({self.id}, {self.name})"


class ContentType(Base):
    __tablename__ = "content_type"
    __table_args__ = {"comment": "The type of content, e.g. news, social media, etc."}

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the content type"
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

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the sentiment type"
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


class AssetGroupType(Base):
    __tablename__ = "asset_group_type"
    __table_args__ = {
        "comment": "The type of asset group, e.g. statistical pairs trading, classical arbitrage, triangular arbitrage, etc."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the asset group type"
    )
    symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The symbol of the asset group type, e.g. PAIRS_TRADING, CLASSICAL_ARBITRAGE, TRIANGULAR_ARBITRAGE, etc.",
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="The name of the asset group type, e.g. Pairs Trading, Classical Arbitrage, Triangular Arbitrage, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="The description of the asset group type, e.g. statistical pairs trading, classical arbitrage, triangular arbitrage, etc.",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the asset group type is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset group type",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the asset group type",
    )

    def __repr__(self):
        return f"{AssetGroupType.__name__}({self.id}, {self.name})"


class TransactionType(Base):
    __tablename__ = "transaction_type"
    __table_args__ = {
        "comment": "The type of transaction, e.g. buy, sell, transfer, short, cover, etc."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the transaction type"
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

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the transaction status type"
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
