import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import AssetMetadata, Metadata, ProviderAssetMetadata, ProviderMetadata
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.metadata import (
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataHistoryEntry,
    MetadataHistoryUpdate,
)

# ---------------------------------------------------------------------------
# Asset Metadata
# ---------------------------------------------------------------------------


def get_latest_asset_metadata(db: Session, asset_id: uuid.UUID) -> list[MetadataEntrySchema]:
    query = (
        select(AssetMetadata)
        .options(joinedload(AssetMetadata.metadata_type))
        .where(AssetMetadata.asset_id == asset_id)
        .order_by(AssetMetadata.metadata_id, AssetMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _dedup_metadata_rows(rows)


def create_asset_metadata_entry(
    db: Session, asset_id: uuid.UUID, data: MetadataEntryCreate
) -> MetadataEntrySchema:
    record = AssetMetadata(
        timestamp=data.timestamp or datetime.datetime.now(datetime.UTC),
        asset_id=asset_id,
        metadata_id=data.metadata_id,
        value=data.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=record.metadata_id,
        metadata_name=md.name if md else "",
        value=record.value,
        timestamp=record.timestamp,
    )


def get_asset_metadata_history(
    db: Session, asset_id: uuid.UUID, metadata_id: uuid.UUID
) -> list[MetadataHistoryEntry]:
    query = (
        select(AssetMetadata)
        .where(
            AssetMetadata.asset_id == asset_id,
            AssetMetadata.metadata_id == metadata_id,
        )
        .order_by(AssetMetadata.timestamp.desc())
    )
    rows = db.execute(query).scalars().all()
    return [
        MetadataHistoryEntry(
            timestamp=r.timestamp,
            value=r.value,
            created_at=r.created_at,
        )
        for r in rows
    ]


def delete_latest_asset_metadata(db: Session, asset_id: uuid.UUID, metadata_id: uuid.UUID) -> None:
    query = (
        select(AssetMetadata)
        .where(
            AssetMetadata.asset_id == asset_id,
            AssetMetadata.metadata_id == metadata_id,
        )
        .order_by(AssetMetadata.timestamp.desc())
        .limit(1)
    )
    row = db.execute(query).scalar_one_or_none()
    if not row:
        raise NotFoundError("Metadata entry not found")
    db.delete(row)
    db.commit()


def update_asset_metadata_entry(
    db: Session,
    asset_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime,
    data: MetadataHistoryUpdate,
) -> MetadataHistoryEntry:
    row = db.get(AssetMetadata, (timestamp, asset_id, metadata_id))
    if not row:
        raise NotFoundError("History entry not found")
    new_ts = data.timestamp if data.timestamp is not None else timestamp
    new_val = data.value if data.value is not None else row.value
    if new_ts != timestamp:
        db.delete(row)
        db.flush()
        row = AssetMetadata(
            timestamp=new_ts,
            asset_id=asset_id,
            metadata_id=metadata_id,
            value=new_val,
        )
        db.add(row)
    else:
        row.value = new_val
    db.commit()
    db.refresh(row)
    return MetadataHistoryEntry(timestamp=row.timestamp, value=row.value, created_at=row.created_at)


def delete_asset_metadata_entry(
    db: Session,
    asset_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime,
) -> None:
    row = db.get(AssetMetadata, (timestamp, asset_id, metadata_id))
    if not row:
        raise NotFoundError("History entry not found")
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Provider Metadata
# ---------------------------------------------------------------------------


def get_latest_provider_metadata(db: Session, provider_id: uuid.UUID) -> list[MetadataEntrySchema]:
    query = (
        select(ProviderMetadata)
        .options(joinedload(ProviderMetadata.metadata_type))
        .where(ProviderMetadata.provider_id == provider_id)
        .order_by(ProviderMetadata.metadata_id, ProviderMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _dedup_metadata_rows(rows)


def create_provider_metadata_entry(
    db: Session, provider_id: uuid.UUID, data: MetadataEntryCreate
) -> MetadataEntrySchema:
    record = ProviderMetadata(
        timestamp=data.timestamp or datetime.datetime.now(datetime.UTC),
        provider_id=provider_id,
        metadata_id=data.metadata_id,
        value=data.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=record.metadata_id,
        metadata_name=md.name if md else "",
        value=record.value,
        timestamp=record.timestamp,
    )


def get_provider_metadata_history(
    db: Session, provider_id: uuid.UUID, metadata_id: uuid.UUID
) -> list[MetadataHistoryEntry]:
    query = (
        select(ProviderMetadata)
        .where(
            ProviderMetadata.provider_id == provider_id,
            ProviderMetadata.metadata_id == metadata_id,
        )
        .order_by(ProviderMetadata.timestamp.desc())
    )
    rows = db.execute(query).scalars().all()
    return [
        MetadataHistoryEntry(
            timestamp=r.timestamp,
            value=r.value,
            created_at=r.created_at,
        )
        for r in rows
    ]


def delete_latest_provider_metadata(
    db: Session, provider_id: uuid.UUID, metadata_id: uuid.UUID
) -> None:
    query = (
        select(ProviderMetadata)
        .where(
            ProviderMetadata.provider_id == provider_id,
            ProviderMetadata.metadata_id == metadata_id,
        )
        .order_by(ProviderMetadata.timestamp.desc())
        .limit(1)
    )
    row = db.execute(query).scalar_one_or_none()
    if not row:
        raise NotFoundError("Metadata entry not found")
    db.delete(row)
    db.commit()


def update_provider_metadata_entry(
    db: Session,
    provider_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime,
    data: MetadataHistoryUpdate,
) -> MetadataHistoryEntry:
    row = db.get(ProviderMetadata, (timestamp, provider_id, metadata_id))
    if not row:
        raise NotFoundError("History entry not found")
    new_ts = data.timestamp if data.timestamp is not None else timestamp
    new_val = data.value if data.value is not None else row.value
    if new_ts != timestamp:
        db.delete(row)
        db.flush()
        row = ProviderMetadata(
            timestamp=new_ts,
            provider_id=provider_id,
            metadata_id=metadata_id,
            value=new_val,
        )
        db.add(row)
    else:
        row.value = new_val
    db.commit()
    db.refresh(row)
    return MetadataHistoryEntry(timestamp=row.timestamp, value=row.value, created_at=row.created_at)


def delete_provider_metadata_entry(
    db: Session,
    provider_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime,
) -> None:
    row = db.get(ProviderMetadata, (timestamp, provider_id, metadata_id))
    if not row:
        raise NotFoundError("History entry not found")
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Provider-Asset Metadata (using existing ProviderAssetMetadata table)
# ---------------------------------------------------------------------------


def get_latest_provider_asset_metadata(
    db: Session, provider_id: uuid.UUID, asset_id: uuid.UUID
) -> list[MetadataEntrySchema]:
    query = (
        select(ProviderAssetMetadata)
        .options(joinedload(ProviderAssetMetadata.metadata_type))
        .where(
            ProviderAssetMetadata.provider_id == provider_id,
            ProviderAssetMetadata.asset_id == asset_id,
        )
        .order_by(
            ProviderAssetMetadata.metadata_id,
            ProviderAssetMetadata.timestamp.desc(),
        )
    )
    rows = db.execute(query).unique().scalars().all()
    return _dedup_metadata_rows(rows)


def create_provider_asset_metadata_entry(
    db: Session,
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: MetadataEntryCreate,
) -> MetadataEntrySchema:
    record = ProviderAssetMetadata(
        timestamp=data.timestamp or datetime.datetime.now(datetime.UTC),
        provider_id=provider_id,
        asset_id=asset_id,
        metadata_id=data.metadata_id,
        value=data.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=record.metadata_id,
        metadata_name=md.name if md else "",
        value=record.value,
        timestamp=record.timestamp,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dedup_metadata_rows(rows: list[Any]) -> list[MetadataEntrySchema]:
    """Deduplicate metadata rows to return only the latest per metadata_id."""
    seen: set[uuid.UUID] = set()
    results: list[MetadataEntrySchema] = []
    for r in rows:
        if r.metadata_id in seen:
            continue
        seen.add(r.metadata_id)
        results.append(
            MetadataEntrySchema(
                metadata_id=r.metadata_id,
                metadata_name=r.metadata_type.name if r.metadata_type else "",
                value=r.value,
                timestamp=r.timestamp,
            )
        )
    return results
