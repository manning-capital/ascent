import uuid
from typing import Optional

from sqlalchemy import Engine, ForeignKey, String, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base, NamedEntityMixin
from ascent.database.models.descriptors import Metadata
from ascent.database.models.types import ProviderType


class Provider(NamedEntityMixin, Base):
    __tablename__ = "provider"
    __table_args__ = {"comment": "The provider, e.g. data vendor, news, social media, etc."}

    provider_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("provider_type.id"),
        nullable=False,
    )
    provider_type: Mapped["ProviderType"] = relationship("ProviderType")
    provider_external_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    underlying_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("provider.id"),
        nullable=True,
    )
    underlying_provider: Mapped[Optional["Provider"]] = relationship(
        "Provider", remote_side="Provider.id"
    )
    derived_providers: Mapped[list["Provider"]] = relationship(
        "Provider", remote_side="Provider.underlying_provider_id", overlaps="underlying_provider"
    )
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def get_all_assets(
        self,
        engine: Engine,
        asset_ids: list[uuid.UUID] = None,
    ) -> set[Asset]:
        from ascent.database.models.provider_assets import ProviderAssetMetadata

        if asset_ids is None:
            asset_ids = []
        with Session(engine) as session:
            is_active_metadata = session.scalar(
                select(Metadata.id).where(Metadata.name == "is_active")
            )
            if is_active_metadata is None:
                return set()

            latest_timestamps_subq = (
                select(
                    ProviderAssetMetadata.provider_id,
                    ProviderAssetMetadata.asset_id,
                    func.max(ProviderAssetMetadata.timestamp).label("max_timestamp"),
                )
                .where(
                    ProviderAssetMetadata.provider_id == self.id,
                    ProviderAssetMetadata.metadata_id == is_active_metadata,
                    ProviderAssetMetadata.value.astext == "true",
                )
                .group_by(ProviderAssetMetadata.provider_id, ProviderAssetMetadata.asset_id)
                .subquery()
            )

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
                    ProviderAssetMetadata.value.astext == "true",
                    Asset.is_active,
                )
            )

            if asset_ids:
                query = query.where(Asset.id.in_(asset_ids))

            assets = session.scalars(query).all()
            return set(assets)
