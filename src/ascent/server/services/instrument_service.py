import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    Asset,
    Metadata,
    Provider,
    ProviderAssetMetadata,
)
from ascent.database.models.instruments import Instrument
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.instruments import (
    InstrumentCreate,
    InstrumentSchema,
    InstrumentUpdate,
    ProviderAssetLinkCreate,
    ProviderAssetLinkSchema,
)

# ---------------------------------------------------------------------------
# Provider-Asset Links (via ProviderAssetMetadata with "symbol" metadata)
# ---------------------------------------------------------------------------


def _get_or_create_symbol_metadata(db: Session) -> Metadata:
    md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not md:
        md = Metadata(name="symbol", description="Provider-specific asset identifier/symbol")
        db.add(md)
        db.commit()
        db.refresh(md)
    return md


def get_provider_asset_links(
    db: Session,
    provider_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
) -> list[ProviderAssetLinkSchema]:
    symbol_md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not symbol_md:
        return []

    query = (
        select(ProviderAssetMetadata)
        .options(
            joinedload(ProviderAssetMetadata.provider),
            joinedload(ProviderAssetMetadata.asset),
        )
        .where(ProviderAssetMetadata.metadata_id == symbol_md.id)
    )
    if provider_id:
        query = query.where(ProviderAssetMetadata.provider_id == provider_id)
    if asset_id:
        query = query.where(ProviderAssetMetadata.asset_id == asset_id)

    query = query.order_by(
        ProviderAssetMetadata.provider_id,
        ProviderAssetMetadata.asset_id,
        ProviderAssetMetadata.timestamp.desc(),
    )

    rows = db.execute(query).unique().scalars().all()

    # Deduplicate to latest per (provider_id, asset_id)
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    results: list[ProviderAssetLinkSchema] = []
    for r in rows:
        key = (r.provider_id, r.asset_id)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            ProviderAssetLinkSchema(
                provider_id=r.provider_id,
                provider_name=r.provider.name if r.provider else None,
                asset_id=r.asset_id,
                asset_name=r.asset.name if r.asset else None,
                asset_symbol=r.asset.name if r.asset else None,
                identifier=str(r.value) if r.value else "",
                created_at=r.created_at,
            )
        )
    return results


def create_provider_asset_link(
    db: Session, data: ProviderAssetLinkCreate
) -> ProviderAssetLinkSchema:
    symbol_md = _get_or_create_symbol_metadata(db)
    record = ProviderAssetMetadata(
        timestamp=datetime.datetime.now(datetime.UTC),
        provider_id=data.provider_id,
        asset_id=data.asset_id,
        metadata_id=symbol_md.id,
        value=data.identifier,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    provider = db.get(Provider, data.provider_id)
    asset = db.get(Asset, data.asset_id)
    return ProviderAssetLinkSchema(
        provider_id=data.provider_id,
        provider_name=provider.name if provider else None,
        asset_id=data.asset_id,
        asset_name=asset.name if asset else None,
        asset_symbol=asset.name if asset else None,
        identifier=data.identifier,
        created_at=record.created_at,
    )


def delete_provider_asset_link(db: Session, provider_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    symbol_md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not symbol_md:
        raise NotFoundError("Provider-asset link not found")
    rows = db.scalars(
        select(ProviderAssetMetadata).where(
            ProviderAssetMetadata.provider_id == provider_id,
            ProviderAssetMetadata.asset_id == asset_id,
            ProviderAssetMetadata.metadata_id == symbol_md.id,
        )
    ).all()
    if not rows:
        raise NotFoundError("Provider-asset link not found")
    for r in rows:
        db.delete(r)
    db.commit()


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------


def get_instruments(db: Session) -> list[InstrumentSchema]:
    query = (
        select(Instrument)
        .options(
            joinedload(Instrument.provider),
            joinedload(Instrument.from_asset),
            joinedload(Instrument.to_asset),
        )
        .order_by(Instrument.created_at.desc())
    )
    instruments = db.execute(query).unique().scalars().all()
    return [_build_instrument_schema(inst) for inst in instruments]


def get_instrument(db: Session, instrument_id: uuid.UUID) -> InstrumentSchema:
    query = (
        select(Instrument)
        .options(
            joinedload(Instrument.provider),
            joinedload(Instrument.from_asset),
            joinedload(Instrument.to_asset),
        )
        .where(Instrument.id == instrument_id)
    )
    inst = db.execute(query).unique().scalar_one_or_none()
    if not inst:
        raise NotFoundError("Instrument not found")
    return _build_instrument_schema(inst)


def create_instrument(db: Session, data: InstrumentCreate) -> InstrumentSchema:
    # Duplicate check: same (provider_id, from_asset_id, to_asset_id) already exists
    existing = db.scalar(
        select(Instrument).where(
            Instrument.provider_id == data.provider_id,
            Instrument.from_asset_id == data.from_asset_id,
            Instrument.to_asset_id == data.to_asset_id,
        )
    )
    if existing:
        raise ConflictError("An instrument with the same provider and asset pair already exists")

    instrument = Instrument(
        name=data.name,
        display_name=data.display_name,
        instrument_type_id=data.instrument_type_id,
        provider_id=data.provider_id,
        from_asset_id=data.from_asset_id,
        to_asset_id=data.to_asset_id,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return get_instrument(db, instrument.id)


def update_instrument(
    db: Session, instrument_id: uuid.UUID, data: InstrumentUpdate
) -> InstrumentSchema:
    instrument = db.get(Instrument, instrument_id)
    if not instrument:
        raise NotFoundError("Instrument not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument, key, value)
    db.commit()
    db.refresh(instrument)
    return get_instrument(db, instrument.id)


def delete_instrument(db: Session, instrument_id: uuid.UUID) -> None:
    instrument = db.get(Instrument, instrument_id)
    if not instrument:
        raise NotFoundError("Instrument not found")
    db.delete(instrument)
    db.commit()


def _build_instrument_schema(inst: Instrument) -> InstrumentSchema:
    return InstrumentSchema(
        id=inst.id,
        name=inst.name,
        display_name=inst.display_name,
        instrument_type_id=inst.instrument_type_id,
        provider_id=inst.provider_id,
        provider_name=inst.provider.name if inst.provider else None,
        from_asset_id=inst.from_asset_id,
        from_asset_name=inst.from_asset.name if inst.from_asset else None,
        to_asset_id=inst.to_asset_id,
        to_asset_name=inst.to_asset.name if inst.to_asset else None,
        description=inst.description,
        is_active=inst.is_active,
        created_at=inst.created_at,
    )
