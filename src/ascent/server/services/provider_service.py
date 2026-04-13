import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Provider
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.providers import (
    ProviderCreate,
    ProviderDetailSchema,
    ProviderSchema,
    ProviderUpdate,
)
from ascent.server.services.instrument_service import get_provider_asset_links
from ascent.server.services.metadata_service import get_latest_provider_metadata


def _build_provider_schema(p: Provider) -> ProviderSchema:
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


PROVIDER_SORT_COLUMNS = {
    "display_name": Provider.display_name,
    "name": Provider.name,
    "provider_type_name": Provider.provider_type_id,
    "provider_external_code": Provider.provider_external_code,
    "is_active": Provider.is_active,
    "created_at": Provider.created_at,
}


def get_providers(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    is_active: bool | None = None,
    sort_field: str = "name",
    sort_order: str = "asc",
) -> tuple[list[ProviderSchema], int]:
    conditions = []
    if search:
        conditions.append(
            Provider.display_name.ilike(f"%{search}%") | Provider.name.ilike(f"%{search}%")
        )
    if is_active is not None:
        conditions.append(Provider.is_active == is_active)

    count_q = select(func.count()).select_from(Provider)
    if conditions:
        count_q = count_q.where(*conditions)
    total = db.execute(count_q).scalar() or 0

    query = select(Provider).options(joinedload(Provider.provider_type))
    if conditions:
        query = query.where(*conditions)

    sort_col = PROVIDER_SORT_COLUMNS.get(sort_field, Provider.name)
    sort_expr = sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullsfirst()
    query = query.order_by(sort_expr).offset((page - 1) * page_size).limit(page_size)
    providers = db.execute(query).unique().scalars().all()
    return [_build_provider_schema(p) for p in providers], total


def get_provider(db: Session, provider_id: uuid.UUID) -> ProviderSchema:
    query = (
        select(Provider)
        .options(joinedload(Provider.provider_type))
        .where(Provider.id == provider_id)
    )
    p = db.execute(query).unique().scalar_one_or_none()
    if not p:
        raise NotFoundError("Provider not found")
    return _build_provider_schema(p)


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
    existing = db.scalar(select(Provider).where(Provider.name == data.name))
    if existing:
        raise ConflictError(f"A provider with the name '{data.name}' already exists")
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
