import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.descriptors import Attribute, Period
from ascent.database.models.providers import Provider
from ascent.database.models.types import AssetGroupType


class ProviderAssetGroup(Base):
    __tablename__ = "provider_asset_group"
    __table_args__ = {
        "comment": "Groups provider assets for calculating aggregated statistical values between members. Each group contains provider asset pairs that share statistical relationships for cointegration analysis, mean reversion modeling, and linear regression calculations."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the asset group"
    )
    asset_group_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_group_type.id"),
        nullable=False,
        comment="The identifier of the asset group type",
    )
    asset_group_type: Mapped["AssetGroupType"] = relationship("AssetGroupType")
    members: Mapped[list["ProviderAssetGroupMember"]] = relationship(
        "ProviderAssetGroupMember",
        cascade="all, delete-orphan",
        order_by="ProviderAssetGroupMember.order.asc()",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether the asset group is active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset group",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the asset group",
    )

    def __repr__(self):
        return f"{ProviderAssetGroup.__name__}({self.id})"


class ProviderAssetGroupMember(Base):
    __tablename__ = "provider_asset_group_member"
    __table_args__ = {
        "comment": "Maps provider asset pairs to statistical groups for aggregated calculations. Each record represents a pair of assets (from_asset_id, to_asset_id) from a specific provider that belong to a statistical group. Optional order field allows sequencing within groups for hierarchical analysis."
    }

    provider_asset_group_id: Mapped[int] = mapped_column(
        ForeignKey("provider_asset_group.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the provider asset group",
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    from_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the from asset (base asset)",
    )
    from_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the to asset (quote asset)",
    )
    to_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[to_asset_id])
    order: Mapped[int] = mapped_column(
        nullable=False,
        comment="The order of the asset pair within the group (1, 2, 3, etc.). Required field for sequencing members within the group.",
    )
    group: Mapped["ProviderAssetGroup"] = relationship("ProviderAssetGroup", overlaps="members")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset group member",
    )

    def __repr__(self):
        return f"{ProviderAssetGroupMember.__name__}(provider_asset_group_id={self.provider_asset_group_id}, provider_id={self.provider_id}, from_asset_id={self.from_asset_id}, to_asset_id={self.to_asset_id})"


class ProviderAssetGroupAttribute(Base):
    __tablename__ = "provider_asset_group_attribute"
    __table_args__ = {
        "comment": "Stores attributes for provider asset groups without time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new attributes to be added without schema changes.",
        "postgresql_partition_by": "HASH (attribute_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset group attributes",
    )
    provider_asset_group_id: Mapped[int] = mapped_column(
        ForeignKey("provider_asset_group.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider asset group",
    )
    provider_asset_group: Mapped["ProviderAssetGroup"] = relationship("ProviderAssetGroup")
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider asset group at the given timestamp",
    )

    def __repr__(self):
        return f"{ProviderAssetGroupAttribute.__name__}(timestamp={self.timestamp}, provider_asset_group_id={self.provider_asset_group_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class ProviderAssetGroupPeriodAttribute(Base):
    __tablename__ = "provider_asset_group_period_attribute"
    __table_args__ = {
        "comment": "Stores aggregated statistical calculations for provider asset groups across multiple time periods. Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new attributes to be added without schema changes. Periods are defined in the Period table for reusability.",
        "postgresql_partition_by": "HASH (attribute_id, period_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        primary_key=True,
        comment="The timestamp of the provider asset group attributes",
    )
    provider_asset_group_id: Mapped[int] = mapped_column(
        ForeignKey("provider_asset_group.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider asset group",
    )
    provider_asset_group: Mapped["ProviderAssetGroup"] = relationship("ProviderAssetGroup")
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
        comment="The value of the attribute for the provider asset group at the given timestamp and period",
    )

    def __repr__(self):
        return f"{ProviderAssetGroupPeriodAttribute.__name__}(timestamp={self.timestamp}, provider_asset_group_id={self.provider_asset_group_id}, period_id={self.period_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"
