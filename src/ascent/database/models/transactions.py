import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.portfolio import Portfolio
from ascent.database.models.types import TransactionStatusType, TransactionType


class Transaction(Base):
    __tablename__ = "transaction"
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
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the source asset in the exchange. Represents the asset being exchanged from.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the destination asset in the exchange. Represents the asset being exchanged to.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    quantity: Mapped[float] = mapped_column(
        nullable=False, comment="The number of units/shares in the transaction"
    )
    price: Mapped[float] = mapped_column(
        nullable=False,
        comment="The exchange price from the from_asset to the to_asset. Represents the price per unit of the to_asset in terms of the from_asset. For example, if buying 1 BTC with 50000 USD, price would be 50000 (1 BTC costs 50000 USD).",
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
        back_populates="transaction",
        order_by="TransactionStatus.timestamp.asc()",
    )

    def __repr__(self):
        return f"{Transaction.__name__}(id={self.id}, timestamp={self.timestamp}, transaction_type={self.transaction_type}, portfolio_id={self.portfolio_id})"


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
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
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
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the transaction",
    )
    transaction: Mapped["Transaction"] = relationship("Transaction", overlaps="groups")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the transaction group member",
    )

    def __repr__(self):
        return f"{TransactionGroupMember.__name__}(transaction_group_id={self.transaction_group_id}, transaction_id={self.transaction_id})"


class TransactionStatus(Base):
    __tablename__ = "transaction_status"
    __table_args__ = {
        "comment": "Time series table storing status updates for transactions. Tracks the status history of transactions over time, allowing for audit trails and status change monitoring."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp when the status was recorded",
    )
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the transaction",
    )
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="statuses")
    transaction_status_type_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_status_type.id"),
        nullable=False,
        comment="The identifier of the transaction status type",
    )
    transaction_status_type: Mapped["TransactionStatusType"] = relationship("TransactionStatusType")

    def __repr__(self):
        return f"{TransactionStatus.__name__}(timestamp={self.timestamp}, transaction_id={self.transaction_id}, transaction_status_type_id={self.transaction_status_type_id})"
