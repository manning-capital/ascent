import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, func, mapped_column, relationship

from summit.database.models.assets import Asset
from summit.database.models.base import Base
from summit.database.models.types import TransactionStatusType, TransactionType
from summit.database.models.portfolio import Portfolio


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transaction"
    __table_args__ = {
        "comment": "Represents individual portfolio transactions including buys, sells, and transfers. Used to track all asset movements within and between portfolios."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the transaction"
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False, comment="The date and time when the transaction occurred"
    )
    transaction_type_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_type.id"),
        nullable=False,
        comment="The identifier of the transaction type",
    )
    transaction_type: Mapped["TransactionType"] = relationship("TransactionType")
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio.id"),
        nullable=False,
        comment="The identifier of the portfolio this transaction belongs to",
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="transactions")
    from_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the source asset in the transaction (e.g., cash for buys, the asset being sold for sells)",
    )
    from_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the destination asset in the transaction (e.g., the asset being bought for buys, cash for sells)",
    )
    to_asset: Mapped[Optional["Asset"]] = relationship("Asset", foreign_keys=[to_asset_id])
    quantity: Mapped[float] = mapped_column(
        nullable=False, comment="The number of units/shares in the transaction"
    )
    price: Mapped[float] = mapped_column(
        nullable=False, comment="The price per unit at which the transaction occurred"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the transaction",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the transaction",
    )

    # Relationship to groups
    groups: Mapped[list["TransactionGroup"]] = relationship(
        "TransactionGroup",
        secondary="transaction_group_member",
        back_populates="transactions",
    )

    # Relationship to status history
    statuses: Mapped[list["TransactionStatus"]] = relationship(
        "TransactionStatus",
        back_populates="portfolio_transaction",
        order_by="TransactionStatus.timestamp.asc()",
    )

    def __repr__(self):
        return f"{PortfolioTransaction.__name__}(id={self.id}, timestamp={self.timestamp}, transaction_type={self.transaction_type}, portfolio_id={self.portfolio_id})"


class TransactionGroup(Base):
    __tablename__ = "transaction_group"
    __table_args__ = {
        "comment": "Groups related transactions together for market neutral and paired trading strategies. Used to link offsetting long and short positions."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the transaction group"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp when this group was created",
    )

    # Relationship to transactions
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(
        "PortfolioTransaction",
        secondary="transaction_group_member",
        back_populates="groups",
    )

    def __repr__(self):
        return f"{TransactionGroup.__name__}(id={self.id})"


class TransactionGroupMember(Base):
    __tablename__ = "transaction_group_member"
    __table_args__ = {
        "comment": "Junction table linking transactions to their groups. Enables many-to-many relationship between transactions and groups."
    }

    transaction_group_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_group.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the transaction group",
    )
    transaction_group: Mapped["TransactionGroup"] = relationship(
        "TransactionGroup", overlaps="transactions"
    )
    portfolio_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_transaction.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the portfolio transaction",
    )
    portfolio_transaction: Mapped["PortfolioTransaction"] = relationship(
        "PortfolioTransaction", overlaps="groups"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the transaction group member",
    )

    def __repr__(self):
        return f"{TransactionGroupMember.__name__}(transaction_group_id={self.transaction_group_id}, portfolio_transaction_id={self.portfolio_transaction_id})"


class TransactionStatus(Base):
    __tablename__ = "transaction_status"
    __table_args__ = {
        "comment": "Time series table storing status updates for portfolio transactions. Tracks the status history of transactions over time, allowing for audit trails and status change monitoring."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp when the status was recorded",
    )
    portfolio_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_transaction.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the portfolio transaction",
    )
    portfolio_transaction: Mapped["PortfolioTransaction"] = relationship(
        "PortfolioTransaction", back_populates="statuses"
    )
    transaction_status_type_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_status_type.id"),
        nullable=False,
        comment="The identifier of the transaction status type",
    )
    transaction_status_type: Mapped["TransactionStatusType"] = relationship("TransactionStatusType")

    def __repr__(self):
        return f"{TransactionStatus.__name__}(timestamp={self.timestamp}, portfolio_transaction_id={self.portfolio_transaction_id}, transaction_status_type_id={self.transaction_status_type_id})"
