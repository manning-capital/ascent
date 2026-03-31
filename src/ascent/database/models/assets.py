import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.types import AssetType


class Asset(NamedEntityMixin, Base):
    __tablename__ = "asset"
    __table_args__ = {"comment": "The asset, e.g. stock, bond, currency, etc."}

    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        nullable=False,
    )
    asset_type: Mapped["AssetType"] = relationship("AssetType")
    underlying_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
    )
    underlying_asset: Mapped[Optional["Asset"]] = relationship("Asset", remote_side="Asset.id")
    derived_assets: Mapped[list["Asset"]] = relationship(
        "Asset", remote_side="Asset.underlying_asset_id", overlaps="underlying_asset"
    )
