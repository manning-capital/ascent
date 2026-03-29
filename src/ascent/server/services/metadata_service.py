import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import AssetMetadata, Metadata, ProviderAssetMetadata, ProviderMetadata
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.metadata import (
    BatchMetadataCreate,
    BulkHistoryUpdate,
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataFieldInfo,
    MetadataHistoryEntry,
    MetadataHistoryGrid,
    MetadataHistoryUpdate,
    MetadataSnapshotRow,
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
        metadata_display_name=md.display_name if md else None,
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
        metadata_display_name=md.display_name if md else None,
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
# Batch create
# ---------------------------------------------------------------------------


def batch_create_asset_metadata(
    db: Session, asset_id: uuid.UUID, data: BatchMetadataCreate
) -> list[MetadataEntrySchema]:
    results: list[MetadataEntrySchema] = []
    for entry in data.entries:
        record = AssetMetadata(
            timestamp=data.timestamp,
            asset_id=asset_id,
            metadata_id=entry.metadata_id,
            value=entry.value,
        )
        db.add(record)
    db.commit()
    for entry in data.entries:
        md = db.get(Metadata, entry.metadata_id)
        results.append(
            MetadataEntrySchema(
                metadata_id=entry.metadata_id,
                metadata_name=md.name if md else "",
                metadata_display_name=md.display_name if md else None,
                value=entry.value,
                timestamp=data.timestamp,
            )
        )
    return results


def batch_create_provider_metadata(
    db: Session, provider_id: uuid.UUID, data: BatchMetadataCreate
) -> list[MetadataEntrySchema]:
    results: list[MetadataEntrySchema] = []
    for entry in data.entries:
        record = ProviderMetadata(
            timestamp=data.timestamp,
            provider_id=provider_id,
            metadata_id=entry.metadata_id,
            value=entry.value,
        )
        db.add(record)
    db.commit()
    for entry in data.entries:
        md = db.get(Metadata, entry.metadata_id)
        results.append(
            MetadataEntrySchema(
                metadata_id=entry.metadata_id,
                metadata_name=md.name if md else "",
                metadata_display_name=md.display_name if md else None,
                value=entry.value,
                timestamp=data.timestamp,
            )
        )
    return results


# ---------------------------------------------------------------------------
# History grid
# ---------------------------------------------------------------------------


def _build_history_grid(rows: list, metadata_model) -> MetadataHistoryGrid:
    """Build a MetadataHistoryGrid from raw metadata rows."""
    # Collect field info and group values by timestamp
    fields_map: dict[uuid.UUID, MetadataFieldInfo] = {}
    snapshots_map: dict[datetime.datetime, dict[str, Any]] = {}

    for r in rows:
        mid = r.metadata_id
        if mid not in fields_map and r.metadata_type:
            fields_map[mid] = MetadataFieldInfo(
                metadata_id=mid,
                metadata_name=r.metadata_type.name,
                metadata_display_name=r.metadata_type.display_name,
                value_type=r.metadata_type.value_type,
            )

        ts = r.timestamp
        if ts not in snapshots_map:
            snapshots_map[ts] = {}
        snapshots_map[ts][str(mid)] = r.value

    fields = sorted(fields_map.values(), key=lambda f: f.metadata_name)
    snapshots = [
        MetadataSnapshotRow(timestamp=ts, values=vals)
        for ts, vals in sorted(snapshots_map.items(), reverse=True)
    ]
    return MetadataHistoryGrid(fields=fields, snapshots=snapshots)


def get_asset_metadata_history_grid(db: Session, asset_id: uuid.UUID) -> MetadataHistoryGrid:
    query = (
        select(AssetMetadata)
        .options(joinedload(AssetMetadata.metadata_type))
        .where(AssetMetadata.asset_id == asset_id)
        .order_by(AssetMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _build_history_grid(rows, AssetMetadata)


def get_provider_metadata_history_grid(db: Session, provider_id: uuid.UUID) -> MetadataHistoryGrid:
    query = (
        select(ProviderMetadata)
        .options(joinedload(ProviderMetadata.metadata_type))
        .where(ProviderMetadata.provider_id == provider_id)
        .order_by(ProviderMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _build_history_grid(rows, ProviderMetadata)


# ---------------------------------------------------------------------------
# Bulk history update
# ---------------------------------------------------------------------------


def bulk_update_asset_metadata_history(
    db: Session, asset_id: uuid.UUID, data: BulkHistoryUpdate
) -> None:
    # Process deletes first
    for d in data.deletes:
        if d.metadata_id:
            row = db.get(AssetMetadata, (d.timestamp, asset_id, d.metadata_id))
            if row:
                db.delete(row)
        else:
            # Delete all entries at this timestamp
            rows = (
                db.execute(
                    select(AssetMetadata).where(
                        AssetMetadata.asset_id == asset_id,
                        AssetMetadata.timestamp == d.timestamp,
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                db.delete(row)

    db.flush()

    # Process updates (value changes and timestamp moves)
    for u in data.updates:
        row = db.get(AssetMetadata, (u.old_timestamp, asset_id, u.metadata_id))
        if not row:
            continue
        new_ts = u.new_timestamp if u.new_timestamp is not None else u.old_timestamp
        if new_ts != u.old_timestamp:
            db.delete(row)
            db.flush()
            new_row = AssetMetadata(
                timestamp=new_ts,
                asset_id=asset_id,
                metadata_id=u.metadata_id,
                value=u.value,
            )
            db.add(new_row)
        else:
            row.value = u.value

    db.flush()

    # Process inserts
    for i in data.inserts:
        record = AssetMetadata(
            timestamp=i.timestamp,
            asset_id=asset_id,
            metadata_id=i.metadata_id,
            value=i.value,
        )
        db.add(record)

    db.commit()


def bulk_update_provider_metadata_history(
    db: Session, provider_id: uuid.UUID, data: BulkHistoryUpdate
) -> None:
    for d in data.deletes:
        if d.metadata_id:
            row = db.get(ProviderMetadata, (d.timestamp, provider_id, d.metadata_id))
            if row:
                db.delete(row)
        else:
            rows = (
                db.execute(
                    select(ProviderMetadata).where(
                        ProviderMetadata.provider_id == provider_id,
                        ProviderMetadata.timestamp == d.timestamp,
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                db.delete(row)

    db.flush()

    for u in data.updates:
        row = db.get(ProviderMetadata, (u.old_timestamp, provider_id, u.metadata_id))
        if not row:
            continue
        new_ts = u.new_timestamp if u.new_timestamp is not None else u.old_timestamp
        if new_ts != u.old_timestamp:
            db.delete(row)
            db.flush()
            new_row = ProviderMetadata(
                timestamp=new_ts,
                provider_id=provider_id,
                metadata_id=u.metadata_id,
                value=u.value,
            )
            db.add(new_row)
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        record = ProviderMetadata(
            timestamp=i.timestamp,
            provider_id=provider_id,
            metadata_id=i.metadata_id,
            value=i.value,
        )
        db.add(record)

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
        metadata_display_name=md.display_name if md else None,
        value=record.value,
        timestamp=record.timestamp,
    )


def batch_create_provider_asset_metadata(
    db: Session,
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: BatchMetadataCreate,
) -> list[MetadataEntrySchema]:
    results: list[MetadataEntrySchema] = []
    for entry in data.entries:
        record = ProviderAssetMetadata(
            timestamp=data.timestamp,
            provider_id=provider_id,
            asset_id=asset_id,
            metadata_id=entry.metadata_id,
            value=entry.value,
        )
        db.add(record)
    db.commit()
    for entry in data.entries:
        md = db.get(Metadata, entry.metadata_id)
        results.append(
            MetadataEntrySchema(
                metadata_id=entry.metadata_id,
                metadata_name=md.name if md else "",
                metadata_display_name=md.display_name if md else None,
                value=entry.value,
                timestamp=data.timestamp,
            )
        )
    return results


def get_provider_asset_metadata_history_grid(
    db: Session, provider_id: uuid.UUID, asset_id: uuid.UUID
) -> MetadataHistoryGrid:
    query = (
        select(ProviderAssetMetadata)
        .options(joinedload(ProviderAssetMetadata.metadata_type))
        .where(
            ProviderAssetMetadata.provider_id == provider_id,
            ProviderAssetMetadata.asset_id == asset_id,
        )
        .order_by(ProviderAssetMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _build_history_grid(rows, ProviderAssetMetadata)


def bulk_update_provider_asset_metadata_history(
    db: Session,
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: BulkHistoryUpdate,
) -> None:
    for d in data.deletes:
        if d.metadata_id:
            row = db.get(ProviderAssetMetadata, (d.timestamp, provider_id, asset_id, d.metadata_id))
            if row:
                db.delete(row)
        else:
            rows = (
                db.execute(
                    select(ProviderAssetMetadata).where(
                        ProviderAssetMetadata.provider_id == provider_id,
                        ProviderAssetMetadata.asset_id == asset_id,
                        ProviderAssetMetadata.timestamp == d.timestamp,
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                db.delete(row)

    db.flush()

    for u in data.updates:
        row = db.get(ProviderAssetMetadata, (u.old_timestamp, provider_id, asset_id, u.metadata_id))
        if not row:
            continue
        new_ts = u.new_timestamp if u.new_timestamp is not None else u.old_timestamp
        if new_ts != u.old_timestamp:
            db.delete(row)
            db.flush()
            new_row = ProviderAssetMetadata(
                timestamp=new_ts,
                provider_id=provider_id,
                asset_id=asset_id,
                metadata_id=u.metadata_id,
                value=u.value,
            )
            db.add(new_row)
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        record = ProviderAssetMetadata(
            timestamp=i.timestamp,
            provider_id=provider_id,
            asset_id=asset_id,
            metadata_id=i.metadata_id,
            value=i.value,
        )
        db.add(record)

    db.commit()


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
                metadata_display_name=r.metadata_type.display_name if r.metadata_type else None,
                value=r.value,
                timestamp=r.timestamp,
            )
        )
    return results
