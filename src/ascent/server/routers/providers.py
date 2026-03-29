import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.metadata import (
    BatchMetadataCreate,
    BulkHistoryUpdate,
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataHistoryEntry,
    MetadataHistoryGrid,
    MetadataHistoryUpdate,
)
from ascent.server.schemas.providers import (
    ProviderCreate,
    ProviderDetailSchema,
    ProviderSchema,
    ProviderUpdate,
)
from ascent.server.services import metadata_service, provider_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderSchema])
def list_providers(db: Session = Depends(get_db)):
    return provider_service.get_providers(db)


@router.get("/{provider_id}", response_model=ProviderDetailSchema)
def get_provider(provider_id: uuid.UUID, db: Session = Depends(get_db)):
    return provider_service.get_provider_detail(db, provider_id)


@router.post("", status_code=201)
def create_provider(data: ProviderCreate, db: Session = Depends(get_db)):
    return provider_service.create_provider(db, data)


@router.put("/{provider_id}")
def update_provider(provider_id: uuid.UUID, data: ProviderUpdate, db: Session = Depends(get_db)):
    return provider_service.update_provider(db, provider_id, data)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: uuid.UUID, db: Session = Depends(get_db)):
    provider_service.delete_provider(db, provider_id)


# ---------------------------------------------------------------------------
# Provider Metadata
# ---------------------------------------------------------------------------


@router.get("/{provider_id}/metadata", response_model=list[MetadataEntrySchema])
def list_provider_metadata(provider_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_latest_provider_metadata(db, provider_id)


@router.post("/{provider_id}/metadata", status_code=201, response_model=MetadataEntrySchema)
def create_provider_metadata(
    provider_id: uuid.UUID, data: MetadataEntryCreate, db: Session = Depends(get_db)
):
    return metadata_service.create_provider_metadata_entry(db, provider_id, data)


@router.post(
    "/{provider_id}/metadata/batch", status_code=201, response_model=list[MetadataEntrySchema]
)
def batch_create_provider_metadata(
    provider_id: uuid.UUID, data: BatchMetadataCreate, db: Session = Depends(get_db)
):
    return metadata_service.batch_create_provider_metadata(db, provider_id, data)


@router.get("/{provider_id}/metadata/history", response_model=MetadataHistoryGrid)
def get_provider_metadata_history_grid(provider_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_provider_metadata_history_grid(db, provider_id)


@router.put("/{provider_id}/metadata/history/bulk", status_code=204)
def bulk_update_provider_metadata_history(
    provider_id: uuid.UUID, data: BulkHistoryUpdate, db: Session = Depends(get_db)
):
    metadata_service.bulk_update_provider_metadata_history(db, provider_id, data)


@router.get(
    "/{provider_id}/metadata/{metadata_id}/history",
    response_model=list[MetadataHistoryEntry],
)
def get_provider_metadata_history(
    provider_id: uuid.UUID, metadata_id: uuid.UUID, db: Session = Depends(get_db)
):
    return metadata_service.get_provider_metadata_history(db, provider_id, metadata_id)


@router.delete("/{provider_id}/metadata/{metadata_id}", status_code=204)
def delete_provider_metadata(
    provider_id: uuid.UUID, metadata_id: uuid.UUID, db: Session = Depends(get_db)
):
    metadata_service.delete_latest_provider_metadata(db, provider_id, metadata_id)


@router.put(
    "/{provider_id}/metadata/{metadata_id}/history",
    response_model=MetadataHistoryEntry,
)
def update_provider_metadata_entry(
    provider_id: uuid.UUID,
    metadata_id: uuid.UUID,
    data: MetadataHistoryUpdate,
    timestamp: datetime.datetime = Query(...),
    db: Session = Depends(get_db),
):
    return metadata_service.update_provider_metadata_entry(
        db, provider_id, metadata_id, timestamp, data
    )


@router.delete(
    "/{provider_id}/metadata/{metadata_id}/history",
    status_code=204,
)
def delete_provider_metadata_entry(
    provider_id: uuid.UUID,
    metadata_id: uuid.UUID,
    timestamp: datetime.datetime = Query(...),
    db: Session = Depends(get_db),
):
    metadata_service.delete_provider_metadata_entry(db, provider_id, metadata_id, timestamp)
