import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Asset
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.assets import AssetCreate, AssetDetailSchema, AssetSchema, AssetUpdate
from ascent.server.services.instrument_service import get_provider_asset_links
from ascent.server.services.metadata_service import get_latest_asset_metadata


def get_assets(db: Session) -> list[AssetSchema]:
    query = select(Asset).options(joinedload(Asset.asset_type)).order_by(Asset.name)
    assets = db.execute(query).unique().scalars().all()
    return [
        AssetSchema(
            id=a.id,
            asset_type_id=a.asset_type_id,
            asset_type_name=a.asset_type.display_name if a.asset_type else None,
            name=a.name,
            display_name=a.display_name,
            description=a.description,
            underlying_asset_id=a.underlying_asset_id,
            is_active=a.is_active,
            created_at=a.created_at,
        )
        for a in assets
    ]


def get_asset(db: Session, asset_id: uuid.UUID) -> AssetDetailSchema:
    query = select(Asset).options(joinedload(Asset.asset_type)).where(Asset.id == asset_id)
    a = db.execute(query).unique().scalar_one_or_none()
    if not a:
        raise NotFoundError("Asset not found")
    metadata = get_latest_asset_metadata(db, asset_id)
    provider_links = get_provider_asset_links(db, asset_id=asset_id)
    return AssetDetailSchema(
        id=a.id,
        asset_type_id=a.asset_type_id,
        asset_type_name=a.asset_type.display_name if a.asset_type else None,
        name=a.name,
        display_name=a.display_name,
        description=a.description,
        underlying_asset_id=a.underlying_asset_id,
        is_active=a.is_active,
        created_at=a.created_at,
        metadata=metadata,
        provider_links=provider_links,
    )


def create_asset(db: Session, data: AssetCreate) -> Asset:
    existing = db.scalar(select(Asset).where(Asset.name == data.name))
    if existing:
        raise ConflictError(f"An asset with the name '{data.name}' already exists")
    asset = Asset(**data.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(db: Session, asset_id: uuid.UUID, data: AssetUpdate) -> Asset:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise NotFoundError("Asset not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, asset_id: uuid.UUID) -> None:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise NotFoundError("Asset not found")
    db.delete(asset)
    db.commit()
