import datetime
import uuid
from typing import Optional

from sqlalchemy import Engine, ForeignKey, String, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.descriptors import Metadata
from ascent.database.models.types import ProviderType


class Provider(Base):
    __tablename__ = "provider"
    __table_args__ = {"comment": "The provider, e.g. data vendor, news, social media, etc."}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, comment="The unique identifier of the provider"
    )
    provider_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider_type.id"),
        nullable=False,
        comment="The identifier of the provider type",
    )
    provider_type: Mapped["ProviderType"] = relationship("ProviderType")
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the provider"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the provider"
    )
    provider_external_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="The external code of the provider, this is used to identify the provider in the provider's system. For example, for a news provider, it could be the name of the provider or an internal ID.",
    )
    underlying_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
        comment="The identifier of the underlying provider",
    )
    underlying_provider: Mapped[Optional["Provider"]] = relationship("Provider", remote_side=[id])
    derived_providers: Mapped[list["Provider"]] = relationship(
        "Provider", remote_side=[underlying_provider_id], overlaps="underlying_provider"
    )
    url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The URL of the provider"
    )
    image_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The URL of the provider's image"
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the provider is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the provider",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the provider",
    )

    def __repr__(self):
        return f"{Provider.__name__}({self.id}, {self.name})"

    def get_all_assets(
        self,
        engine: Engine,
        asset_ids: list[uuid.UUID] = None,
    ) -> set[Asset]:
        from ascent.database.models.provider_assets import ProviderAssetMetadata

        if asset_ids is None:
            asset_ids = []
        with Session(engine) as session:
            # Get the metadata_id for "is_active"
            is_active_metadata = session.scalar(
                select(Metadata.id).where(Metadata.name == "is_active")
            )
            if is_active_metadata is None:
                return set()

            # Subquery to get the latest timestamp for each provider_id, asset_id combination
            # where is_active is True (JSON boolean true)
            latest_timestamps_subq = (
                select(
                    ProviderAssetMetadata.provider_id,
                    ProviderAssetMetadata.asset_id,
                    func.max(ProviderAssetMetadata.timestamp).label("max_timestamp"),
                )
                .where(
                    ProviderAssetMetadata.provider_id == self.id,
                    ProviderAssetMetadata.metadata_id == is_active_metadata,
                    ProviderAssetMetadata.value.astext == "true",  # JSON boolean true as text
                )
                .group_by(ProviderAssetMetadata.provider_id, ProviderAssetMetadata.asset_id)
                .subquery()
            )

            # Query to get assets that have provider_asset_metadata entries with is_active=True
            # at the latest timestamps
            query = (
                select(Asset)
                .join(
                    ProviderAssetMetadata,
                    Asset.id == ProviderAssetMetadata.asset_id,
                )
                .join(
                    latest_timestamps_subq,
                    (ProviderAssetMetadata.provider_id == latest_timestamps_subq.c.provider_id)
                    & (ProviderAssetMetadata.asset_id == latest_timestamps_subq.c.asset_id)
                    & (ProviderAssetMetadata.timestamp == latest_timestamps_subq.c.max_timestamp),
                )
                .where(
                    ProviderAssetMetadata.provider_id == self.id,
                    ProviderAssetMetadata.metadata_id == is_active_metadata,
                    ProviderAssetMetadata.value.astext == "true",  # JSON boolean true as text
                    Asset.is_active,
                )
            )

            # Add asset ID filter if provided
            if asset_ids:
                query = query.where(Asset.id.in_(asset_ids))

            # Execute query and return results as a set
            assets = session.scalars(query).all()
            return set(assets)
