import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Provider
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.providers import (
    ProviderCreate,
    ProviderDetailSchema,
    ProviderSchema,
    ProviderUpdate,
)
from ascent.server.services.instrument_service import get_provider_asset_links
from ascent.server.services.metadata_service import get_latest_provider_metadata


def get_providers(db: Session) -> list[ProviderSchema]:
    query = select(Provider).options(joinedload(Provider.provider_type)).order_by(Provider.name)
    providers = db.execute(query).unique().scalars().all()
    return [
        ProviderSchema(
            id=p.id,
            provider_type_id=p.provider_type_id,
            provider_type_name=p.provider_type.display_name if p.provider_type else None,
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            provider_external_code=p.provider_external_code,
            underlying_provider_id=p.underlying_provider_id,
            url=p.url,
            image_url=p.image_url,
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in providers
    ]


def get_provider(db: Session, provider_id: uuid.UUID) -> ProviderSchema:
    query = (
        select(Provider)
        .options(joinedload(Provider.provider_type))
        .where(Provider.id == provider_id)
    )
    p = db.execute(query).unique().scalar_one_or_none()
    if not p:
        raise NotFoundError("Provider not found")
    return ProviderSchema(
        id=p.id,
        provider_type_id=p.provider_type_id,
        provider_type_name=p.provider_type.display_name if p.provider_type else None,
        name=p.name,
        display_name=p.display_name,
        description=p.description,
        provider_external_code=p.provider_external_code,
        underlying_provider_id=p.underlying_provider_id,
        url=p.url,
        image_url=p.image_url,
        is_active=p.is_active,
        created_at=p.created_at,
    )


def get_provider_detail(db: Session, provider_id: uuid.UUID) -> ProviderDetailSchema:
    query = (
        select(Provider)
        .options(joinedload(Provider.provider_type))
        .where(Provider.id == provider_id)
    )
    p = db.execute(query).unique().scalar_one_or_none()
    if not p:
        raise NotFoundError("Provider not found")
    metadata = get_latest_provider_metadata(db, provider_id)
    asset_links = get_provider_asset_links(db, provider_id=provider_id)
    return ProviderDetailSchema(
        id=p.id,
        provider_type_id=p.provider_type_id,
        provider_type_name=p.provider_type.display_name if p.provider_type else None,
        name=p.name,
        display_name=p.display_name,
        description=p.description,
        provider_external_code=p.provider_external_code,
        underlying_provider_id=p.underlying_provider_id,
        url=p.url,
        image_url=p.image_url,
        is_active=p.is_active,
        created_at=p.created_at,
        metadata=metadata,
        asset_links=asset_links,
    )


def create_provider(db: Session, data: ProviderCreate) -> Provider:
    provider = Provider(**data.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def update_provider(db: Session, provider_id: uuid.UUID, data: ProviderUpdate) -> Provider:
    provider = db.get(Provider, provider_id)
    if not provider:
        raise NotFoundError("Provider not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, key, value)
    db.commit()
    db.refresh(provider)
    return provider


def delete_provider(db: Session, provider_id: uuid.UUID) -> None:
    provider = db.get(Provider, provider_id)
    if not provider:
        raise NotFoundError("Provider not found")
    db.delete(provider)
    db.commit()
