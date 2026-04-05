import datetime
import uuid
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    AssetMetadata,
    CompositeMetadata,
    InstrumentMetadata,
    Metadata,
    ProviderAssetMetadata,
    ProviderMetadata,
)
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
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    db.execute(
        insert(AssetMetadata).values(
            timestamp=ts, asset_id=asset_id, metadata_id=data.metadata_id, value=data.value
        )
    )
    db.commit()
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=data.metadata_id,
        metadata_name=md.name if md else "",
        metadata_display_name=md.display_name if md else None,
        value=data.value,
        timestamp=ts,
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
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    db.execute(
        insert(ProviderMetadata).values(
            timestamp=ts, provider_id=provider_id, metadata_id=data.metadata_id, value=data.value
        )
    )
    db.commit()
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=data.metadata_id,
        metadata_name=md.name if md else "",
        metadata_display_name=md.display_name if md else None,
        value=data.value,
        timestamp=ts,
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
    for entry in data.entries:
        db.execute(
            insert(AssetMetadata).values(
                timestamp=data.timestamp,
                asset_id=asset_id,
                metadata_id=entry.metadata_id,
                value=entry.value,
            )
        )
    db.commit()
    results: list[MetadataEntrySchema] = []
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
    for entry in data.entries:
        db.execute(
            insert(ProviderMetadata).values(
                timestamp=data.timestamp,
                provider_id=provider_id,
                metadata_id=entry.metadata_id,
                value=entry.value,
            )
        )
    db.commit()
    results: list[MetadataEntrySchema] = []
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
                config=r.metadata_type.config,
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
            db.execute(
                insert(AssetMetadata).values(
                    timestamp=new_ts,
                    asset_id=asset_id,
                    metadata_id=u.metadata_id,
                    value=u.value,
                )
            )
        else:
            row.value = u.value

    db.flush()

    # Process inserts — use raw insert to avoid sentinel mismatch with
    # composite PK (timestamp precision differences between Python and PG)
    for i in data.inserts:
        db.execute(
            insert(AssetMetadata).values(
                timestamp=i.timestamp,
                asset_id=asset_id,
                metadata_id=i.metadata_id,
                value=i.value,
            )
        )

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
            db.execute(
                insert(ProviderMetadata).values(
                    timestamp=new_ts,
                    provider_id=provider_id,
                    metadata_id=u.metadata_id,
                    value=u.value,
                )
            )
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        db.execute(
            insert(ProviderMetadata).values(
                timestamp=i.timestamp,
                provider_id=provider_id,
                metadata_id=i.metadata_id,
                value=i.value,
            )
        )

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
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    db.execute(
        insert(ProviderAssetMetadata).values(
            timestamp=ts,
            provider_id=provider_id,
            asset_id=asset_id,
            metadata_id=data.metadata_id,
            value=data.value,
        )
    )
    db.commit()
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=data.metadata_id,
        metadata_name=md.name if md else "",
        metadata_display_name=md.display_name if md else None,
        value=data.value,
        timestamp=ts,
    )


def batch_create_provider_asset_metadata(
    db: Session,
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: BatchMetadataCreate,
) -> list[MetadataEntrySchema]:
    for entry in data.entries:
        db.execute(
            insert(ProviderAssetMetadata).values(
                timestamp=data.timestamp,
                provider_id=provider_id,
                asset_id=asset_id,
                metadata_id=entry.metadata_id,
                value=entry.value,
            )
        )
    db.commit()
    results: list[MetadataEntrySchema] = []
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
            db.execute(
                insert(ProviderAssetMetadata).values(
                    timestamp=new_ts,
                    provider_id=provider_id,
                    asset_id=asset_id,
                    metadata_id=u.metadata_id,
                    value=u.value,
                )
            )
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        db.execute(
            insert(ProviderAssetMetadata).values(
                timestamp=i.timestamp,
                provider_id=provider_id,
                asset_id=asset_id,
                metadata_id=i.metadata_id,
                value=i.value,
            )
        )

    db.commit()


# ---------------------------------------------------------------------------
# Instrument Metadata
# ---------------------------------------------------------------------------


def get_latest_instrument_metadata(
    db: Session, instrument_id: uuid.UUID
) -> list[MetadataEntrySchema]:
    query = (
        select(InstrumentMetadata)
        .options(joinedload(InstrumentMetadata.metadata_type))
        .where(InstrumentMetadata.instrument_id == instrument_id)
        .order_by(InstrumentMetadata.metadata_id, InstrumentMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _dedup_metadata_rows(rows)


def create_instrument_metadata_entry(
    db: Session, instrument_id: uuid.UUID, data: MetadataEntryCreate
) -> MetadataEntrySchema:
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    db.execute(
        insert(InstrumentMetadata).values(
            timestamp=ts,
            instrument_id=instrument_id,
            metadata_id=data.metadata_id,
            value=data.value,
        )
    )
    db.commit()
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=data.metadata_id,
        metadata_name=md.name if md else "",
        metadata_display_name=md.display_name if md else None,
        value=data.value,
        timestamp=ts,
    )


def batch_create_instrument_metadata(
    db: Session, instrument_id: uuid.UUID, data: BatchMetadataCreate
) -> list[MetadataEntrySchema]:
    for entry in data.entries:
        db.execute(
            insert(InstrumentMetadata).values(
                timestamp=data.timestamp,
                instrument_id=instrument_id,
                metadata_id=entry.metadata_id,
                value=entry.value,
            )
        )
    db.commit()
    results: list[MetadataEntrySchema] = []
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


def get_instrument_metadata_history_grid(
    db: Session, instrument_id: uuid.UUID
) -> MetadataHistoryGrid:
    query = (
        select(InstrumentMetadata)
        .options(joinedload(InstrumentMetadata.metadata_type))
        .where(InstrumentMetadata.instrument_id == instrument_id)
        .order_by(InstrumentMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _build_history_grid(rows, InstrumentMetadata)


def bulk_update_instrument_metadata_history(
    db: Session, instrument_id: uuid.UUID, data: BulkHistoryUpdate
) -> None:
    for d in data.deletes:
        if d.metadata_id:
            row = db.get(InstrumentMetadata, (d.timestamp, instrument_id, d.metadata_id))
            if row:
                db.delete(row)
        else:
            rows = (
                db.execute(
                    select(InstrumentMetadata).where(
                        InstrumentMetadata.instrument_id == instrument_id,
                        InstrumentMetadata.timestamp == d.timestamp,
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                db.delete(row)

    db.flush()

    for u in data.updates:
        row = db.get(InstrumentMetadata, (u.old_timestamp, instrument_id, u.metadata_id))
        if not row:
            continue
        new_ts = u.new_timestamp if u.new_timestamp is not None else u.old_timestamp
        if new_ts != u.old_timestamp:
            db.delete(row)
            db.flush()
            db.execute(
                insert(InstrumentMetadata).values(
                    timestamp=new_ts,
                    instrument_id=instrument_id,
                    metadata_id=u.metadata_id,
                    value=u.value,
                )
            )
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        db.execute(
            insert(InstrumentMetadata).values(
                timestamp=i.timestamp,
                instrument_id=instrument_id,
                metadata_id=i.metadata_id,
                value=i.value,
            )
        )

    db.commit()


# ---------------------------------------------------------------------------
# Composite Metadata
# ---------------------------------------------------------------------------


def get_latest_composite_metadata(
    db: Session, composite_id: uuid.UUID
) -> list[MetadataEntrySchema]:
    query = (
        select(CompositeMetadata)
        .options(joinedload(CompositeMetadata.metadata_type))
        .where(CompositeMetadata.composite_id == composite_id)
        .order_by(CompositeMetadata.metadata_id, CompositeMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _dedup_metadata_rows(rows)


def create_composite_metadata_entry(
    db: Session, composite_id: uuid.UUID, data: MetadataEntryCreate
) -> MetadataEntrySchema:
    ts = data.timestamp or datetime.datetime.now(datetime.UTC)
    db.execute(
        insert(CompositeMetadata).values(
            timestamp=ts,
            composite_id=composite_id,
            metadata_id=data.metadata_id,
            value=data.value,
        )
    )
    db.commit()
    md = db.get(Metadata, data.metadata_id)
    return MetadataEntrySchema(
        metadata_id=data.metadata_id,
        metadata_name=md.name if md else "",
        metadata_display_name=md.display_name if md else None,
        value=data.value,
        timestamp=ts,
    )


def batch_create_composite_metadata(
    db: Session, composite_id: uuid.UUID, data: BatchMetadataCreate
) -> list[MetadataEntrySchema]:
    for entry in data.entries:
        db.execute(
            insert(CompositeMetadata).values(
                timestamp=data.timestamp,
                composite_id=composite_id,
                metadata_id=entry.metadata_id,
                value=entry.value,
            )
        )
    db.commit()
    results: list[MetadataEntrySchema] = []
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


def get_composite_metadata_history_grid(
    db: Session, composite_id: uuid.UUID
) -> MetadataHistoryGrid:
    query = (
        select(CompositeMetadata)
        .options(joinedload(CompositeMetadata.metadata_type))
        .where(CompositeMetadata.composite_id == composite_id)
        .order_by(CompositeMetadata.timestamp.desc())
    )
    rows = db.execute(query).unique().scalars().all()
    return _build_history_grid(rows, CompositeMetadata)


def bulk_update_composite_metadata_history(
    db: Session, composite_id: uuid.UUID, data: BulkHistoryUpdate
) -> None:
    for d in data.deletes:
        if d.metadata_id:
            row = db.get(CompositeMetadata, (d.timestamp, composite_id, d.metadata_id))
            if row:
                db.delete(row)
        else:
            rows = (
                db.execute(
                    select(CompositeMetadata).where(
                        CompositeMetadata.composite_id == composite_id,
                        CompositeMetadata.timestamp == d.timestamp,
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                db.delete(row)

    db.flush()

    for u in data.updates:
        row = db.get(CompositeMetadata, (u.old_timestamp, composite_id, u.metadata_id))
        if not row:
            continue
        new_ts = u.new_timestamp if u.new_timestamp is not None else u.old_timestamp
        if new_ts != u.old_timestamp:
            db.delete(row)
            db.flush()
            db.execute(
                insert(CompositeMetadata).values(
                    timestamp=new_ts,
                    composite_id=composite_id,
                    metadata_id=u.metadata_id,
                    value=u.value,
                )
            )
        else:
            row.value = u.value

    db.flush()

    for i in data.inserts:
        db.execute(
            insert(CompositeMetadata).values(
                timestamp=i.timestamp,
                composite_id=composite_id,
                metadata_id=i.metadata_id,
                value=i.value,
            )
        )

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
