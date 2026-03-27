import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.assets import AssetCreate, AssetDetailSchema, AssetSchema, AssetUpdate
from ascent.server.schemas.metadata import (
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataHistoryEntry,
    MetadataHistoryUpdate,
)
from ascent.server.services import asset_service, metadata_service

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetSchema])
def list_assets(db: Session = Depends(get_db)):
    return asset_service.get_assets(db)


@router.get("/{asset_id}", response_model=AssetDetailSchema)
def get_asset(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    return asset_service.get_asset(db, asset_id)


@router.post("", status_code=201)
def create_asset(data: AssetCreate, db: Session = Depends(get_db)):
    return asset_service.create_asset(db, data)


@router.put("/{asset_id}")
def update_asset(asset_id: uuid.UUID, data: AssetUpdate, db: Session = Depends(get_db)):
    return asset_service.update_asset(db, asset_id, data)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    asset_service.delete_asset(db, asset_id)


# ---------------------------------------------------------------------------
# Asset Metadata
# ---------------------------------------------------------------------------


@router.get("/{asset_id}/metadata", response_model=list[MetadataEntrySchema])
def list_asset_metadata(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_latest_asset_metadata(db, asset_id)


@router.post("/{asset_id}/metadata", status_code=201, response_model=MetadataEntrySchema)
def create_asset_metadata(
    asset_id: uuid.UUID, data: MetadataEntryCreate, db: Session = Depends(get_db)
):
    return metadata_service.create_asset_metadata_entry(db, asset_id, data)


@router.get(
    "/{asset_id}/metadata/{metadata_id}/history",
    response_model=list[MetadataHistoryEntry],
)
def get_asset_metadata_history(
    asset_id: uuid.UUID, metadata_id: uuid.UUID, db: Session = Depends(get_db)
):
    return metadata_service.get_asset_metadata_history(db, asset_id, metadata_id)


@router.delete("/{asset_id}/metadata/{metadata_id}", status_code=204)
def delete_asset_metadata(
    asset_id: uuid.UUID, metadata_id: uuid.UUID, db: Session = Depends(get_db)
):
    metadata_service.delete_latest_asset_metadata(db, asset_id, metadata_id)


@router.put(
    "/{asset_id}/metadata/{metadata_id}/history",
    response_model=MetadataHistoryEntry,
)
def update_asset_metadata_entry(
    asset_id: uuid.UUID,
    metadata_id: uuid.UUID,
    data: MetadataHistoryUpdate,
    timestamp: datetime.datetime = Query(...),
    db: Session = Depends(get_db),
):
    return metadata_service.update_asset_metadata_entry(db, asset_id, metadata_id, timestamp, data)


@router.delete(
    "/{asset_id}/metadata/{metadata_id}/history",
    status_code=204,
)
def delete_asset_metadata_entry(
    asset_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime = Query(...),
    db: Session = Depends(get_db),
):
    metadata_service.delete_asset_metadata_entry(db, asset_id, metadata_id, timestamp)
