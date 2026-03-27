import datetime
import uuid

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.portfolio import Portfolio
from ascent.database.models.providers import Provider
from ascent.database.models.types import OrderStatusType, OrderType


class Order(Base):
    __tablename__ = "order"
    __table_args__ = {
        "comment": "Represents exchange orders submitted for execution. Tracks order type, side, fill status, and links to the portfolio and trade leg that originated the order."
    }

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the order"
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False, comment="The date and time when the order was submitted"
    )
    order_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("order_type.id"),
        nullable=False,
        comment="The identifier of the order type (MARKET, LIMIT, STOP, etc.)",
    )
    order_type: Mapped["OrderType"] = relationship("OrderType")
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="The side of the order: BUY or SELL",
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=False,
        comment="The identifier of the provider/exchange",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolio.id"),
        nullable=False,
        comment="The identifier of the portfolio this order belongs to",
    )
    portfolio: Mapped["Portfolio"] = relationship("Portfolio")
    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the from asset (base asset)",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the to asset (quote asset)",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    quantity: Mapped[float] = mapped_column(
        nullable=False, comment="The requested number of units/shares in the order"
    )
    price: Mapped[float] = mapped_column(
        nullable=False,
        comment="The order price. For market orders, the estimated price. For limit orders, the limit price.",
    )
    filled_quantity: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The total quantity filled so far. Null before any fills.",
    )
    average_fill_price: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="The volume-weighted average fill price across all fills. Null before any fills.",
    )
    external_order_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="The exchange's order identifier for cross-referencing with the external system",
    )
    time_in_force: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="The time-in-force policy: GTC (Good Til Cancelled), IOC (Immediate Or Cancel), FOK (Fill Or Kill)",
    )
    trade_leg_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("trade_leg.id", name="fk_order_trade_leg_id", use_alter=True),
        nullable=True,
        comment="The identifier of the trade leg this order is for. Null for orders not associated with a trade.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the order record",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the order record",
    )

    # Relationship to status history
    statuses: Mapped[list["OrderStatus"]] = relationship(
        "OrderStatus",
        back_populates="order",
        order_by="OrderStatus.timestamp.asc()",
    )

    def __repr__(self):
        return f"{Order.__name__}(id={self.id}, timestamp={self.timestamp}, side={self.side}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, quantity={self.quantity}, price={self.price})"


class OrderStatus(Base):
    __tablename__ = "order_status"
    __table_args__ = {
        "comment": "Time series table storing status updates for orders. Tracks the status history of orders over time, including error information for rejected or failed orders."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp when the status was recorded",
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("order.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the order",
    )
    order: Mapped["Order"] = relationship("Order", back_populates="statuses")
    order_status_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("order_status_type.id"),
        nullable=False,
        comment="The identifier of the order status type",
    )
    order_status_type: Mapped["OrderStatusType"] = relationship("OrderStatusType")
    error_message: Mapped[str | None] = mapped_column(
        String(5000),
        nullable=True,
        comment="The error message if the order was rejected or failed",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="The error code from the exchange if the order was rejected or failed",
    )

    def __repr__(self):
        return f"{OrderStatus.__name__}(timestamp={self.timestamp}, order_id={self.order_id}, order_status_type_id={self.order_status_type_id})"
