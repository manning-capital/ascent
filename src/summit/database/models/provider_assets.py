import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, func, mapped_column, relationship

from summit.database.models.assets import Asset
from summit.database.models.attributes import Attribute, Period
from summit.database.models.base import Base
from summit.database.models.providers import Provider


class ProviderAsset(Base):
    __tablename__ = "provider_asset"
    __table_args__ = {
        "comment": "The provider asset, is meant to map our internal definitions to the provider's definitions."
    }

    date: Mapped[datetime.date] = mapped_column(
        primary_key=True, comment="The date of the provider asset"
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the asset",
    )
    asset: Mapped["Asset"] = relationship("Asset")
    asset_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The code of the asset, this is used to identify the asset in the provider's system. For example, for a stock, it could be the ticker symbol or an internal ID.",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the provider asset is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the provider asset",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the provider asset",
    )

    def __repr__(self):
        return f"{ProviderAsset.__name__}({self.date}, {self.provider_id}, {self.asset_id})"


class ProviderAssetOrder(Base):
    __tablename__ = "provider_asset_order"
    __table_args__ = {
        "comment": "The provider asset order, will store order data for an asset from a provider."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the provider asset order"
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False, comment="The timestamp of the provider asset order"
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        comment="The identifier of the from asset",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"), nullable=False, comment="The identifier of the to asset"
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    price: Mapped[float] = mapped_column(
        nullable=True, comment="The price of the provider asset order"
    )
    volume: Mapped[float] = mapped_column(
        nullable=True, comment="The volume of the provider asset order"
    )

    def __repr__(self):
        return f"{ProviderAssetOrder.__name__}(id={self.id}, timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, price={self.price}, volume={self.volume})"


class ProviderAssetAttribute(Base):
    __tablename__ = "provider_asset_attribute"
    __table_args__ = {
        "comment": "Stores market data attributes for provider asset markets. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new market data attributes to be added without schema changes."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset market",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the from asset. This is also called the base asset.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the to asset. This is also called the quote asset.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider asset market at the given timestamp",
    )

    def __repr__(self):
        return f"{ProviderAssetAttribute.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class ProviderAssetPeriodAttribute(Base):
    __tablename__ = "provider_asset_period_attribute"
    __table_args__ = {
        "comment": "Stores market data attributes for provider asset markets with time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new market data attributes to be added without schema changes. Periods are defined in the Period table for reusability."
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset market",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the from asset. This is also called the base asset.",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the to asset. This is also called the quote asset.",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    period_id: Mapped[int] = mapped_column(
        ForeignKey("period.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the period used for the calculation",
    )
    period: Mapped["Period"] = relationship("Period")
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider asset market at the given timestamp and period",
    )

    def __repr__(self):
        return f"{ProviderAssetPeriodAttribute.__name__}(timestamp={self.timestamp}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id}, period_id={self.period_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"
