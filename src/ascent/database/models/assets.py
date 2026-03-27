import datetime
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base
from ascent.database.models.types import AssetType


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = {"comment": "The asset, e.g. stock, bond, currency, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the asset"
    )
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset_type.id"),
        nullable=False,
        comment="The identifier of the asset type",
    )
    asset_type: Mapped["AssetType"] = relationship("AssetType")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="The name of the asset")
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the asset"
    )
    symbol: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="The symbol of the asset"
    )
    underlying_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        nullable=True,
        comment="The identifier of the underlying asset",
    )
    underlying_asset: Mapped[Optional["Asset"]] = relationship("Asset", remote_side=[id])
    derived_assets: Mapped[list["Asset"]] = relationship(
        "Asset", remote_side=[underlying_asset_id], overlaps="underlying_asset"
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the asset is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the asset",
    )

    def __repr__(self):
        return f"{Asset.__name__}({self.id}, {self.name})"
