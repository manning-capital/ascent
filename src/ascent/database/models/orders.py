import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.providers import Provider


class Order(Base):
    __tablename__ = "order"
    __table_args__ = {
        "comment": "Represents individual exchange orders. Stores generic order data from providers/exchanges that is not associated with a particular portfolio. Used to track market orders, limit orders, and other exchange order data."
    }

    id: Mapped[int] = mapped_column(primary_key=True, comment="The unique identifier of the order")
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False, comment="The date and time when the order occurred"
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        comment="The identifier of the provider/exchange",
    )
    provider: Mapped["Provider"] = relationship("Provider")
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
        nullable=False, comment="The number of units/shares in the order"
    )
    price: Mapped[float] = mapped_column(
        nullable=False,
        comment="The exchange price from the from_asset to the to_asset. Represents the price per unit of the to_asset in terms of the from_asset. For example, if buying 1 BTC with 50000 USD, price would be 50000 (1 BTC costs 50000 USD).",
    )

    def __repr__(self):
        return f"{Order.__name__}(id={self.id}, timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, quantity={self.quantity}, price={self.price})"
