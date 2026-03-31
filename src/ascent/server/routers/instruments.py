import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.instruments import (
    InstrumentCreate,
    InstrumentSchema,
    InstrumentUpdate,
    ProviderAssetLinkCreate,
    ProviderAssetLinkSchema,
)
from ascent.server.schemas.metadata import (
    BatchMetadataCreate,
    BulkHistoryUpdate,
    EntityUsage,
    MetadataEntryCreate,
    MetadataEntrySchema,
    MetadataHistoryGrid,
)
from ascent.server.services import field_service, instrument_service, metadata_service

router = APIRouter(tags=["provider-assets"])


# ---------------------------------------------------------------------------
# Provider-Asset Links
# ---------------------------------------------------------------------------


@router.get("/provider-assets", response_model=list[ProviderAssetLinkSchema])
def list_provider_asset_links(
    provider_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    return instrument_service.get_provider_asset_links(db, provider_id, asset_id)


@router.post("/provider-assets", status_code=201, response_model=ProviderAssetLinkSchema)
def create_provider_asset_link(data: ProviderAssetLinkCreate, db: Session = Depends(get_db)):
    return instrument_service.create_provider_asset_link(db, data)


@router.delete("/provider-assets/{provider_id}/{asset_id}", status_code=204)
def delete_provider_asset_link(
    provider_id: uuid.UUID, asset_id: uuid.UUID, db: Session = Depends(get_db)
):
    instrument_service.delete_provider_asset_link(db, provider_id, asset_id)


# ---------------------------------------------------------------------------
# Provider-Asset Metadata
# ---------------------------------------------------------------------------


@router.get(
    "/provider-assets/{provider_id}/{asset_id}/metadata",
    response_model=list[MetadataEntrySchema],
)
def list_provider_asset_metadata(
    provider_id: uuid.UUID, asset_id: uuid.UUID, db: Session = Depends(get_db)
):
    return metadata_service.get_latest_provider_asset_metadata(db, provider_id, asset_id)


@router.post(
    "/provider-assets/{provider_id}/{asset_id}/metadata",
    status_code=201,
    response_model=MetadataEntrySchema,
)
def create_provider_asset_metadata(
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: MetadataEntryCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.create_provider_asset_metadata_entry(db, provider_id, asset_id, data)


@router.post(
    "/provider-assets/{provider_id}/{asset_id}/metadata/batch",
    status_code=201,
    response_model=list[MetadataEntrySchema],
)
def batch_create_provider_asset_metadata(
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: BatchMetadataCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.batch_create_provider_asset_metadata(db, provider_id, asset_id, data)


@router.get(
    "/provider-assets/{provider_id}/{asset_id}/metadata/history",
    response_model=MetadataHistoryGrid,
)
def get_provider_asset_metadata_history(
    provider_id: uuid.UUID, asset_id: uuid.UUID, db: Session = Depends(get_db)
):
    return metadata_service.get_provider_asset_metadata_history_grid(db, provider_id, asset_id)


@router.put(
    "/provider-assets/{provider_id}/{asset_id}/metadata/history/bulk",
    status_code=204,
)
def bulk_update_provider_asset_metadata_history(
    provider_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: BulkHistoryUpdate,
    db: Session = Depends(get_db),
):
    metadata_service.bulk_update_provider_asset_metadata_history(db, provider_id, asset_id, data)


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------


@router.get("/instruments", response_model=list[InstrumentSchema])
def list_instruments(db: Session = Depends(get_db)):
    return instrument_service.get_instruments(db)


@router.get("/instruments/{instrument_id}", response_model=InstrumentSchema)
def get_instrument(instrument_id: uuid.UUID, db: Session = Depends(get_db)):
    return instrument_service.get_instrument(db, instrument_id)


@router.get("/instruments/{instrument_id}/usage", response_model=EntityUsage)
def get_instrument_usage(instrument_id: uuid.UUID, db: Session = Depends(get_db)):
    return field_service.get_instrument_usage(db, instrument_id)


@router.post("/instruments", status_code=201, response_model=InstrumentSchema)
def create_instrument(data: InstrumentCreate, db: Session = Depends(get_db)):
    instrument = instrument_service.create_instrument(db, data)
    return instrument_service.get_instrument(db, instrument.id)


@router.put("/instruments/{instrument_id}")
def update_instrument(
    instrument_id: uuid.UUID, data: InstrumentUpdate, db: Session = Depends(get_db)
):
    return instrument_service.update_instrument(db, instrument_id, data)


@router.delete("/instruments/{instrument_id}", status_code=204)
def delete_instrument(instrument_id: uuid.UUID, db: Session = Depends(get_db)):
    instrument_service.delete_instrument(db, instrument_id)


# ---------------------------------------------------------------------------
# Instrument Metadata
# ---------------------------------------------------------------------------


@router.get(
    "/instruments/{instrument_id}/metadata",
    response_model=list[MetadataEntrySchema],
)
def list_instrument_metadata(instrument_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_latest_instrument_metadata(db, instrument_id)


@router.post(
    "/instruments/{instrument_id}/metadata",
    status_code=201,
    response_model=MetadataEntrySchema,
)
def create_instrument_metadata(
    instrument_id: uuid.UUID,
    data: MetadataEntryCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.create_instrument_metadata_entry(db, instrument_id, data)


@router.post(
    "/instruments/{instrument_id}/metadata/batch",
    status_code=201,
    response_model=list[MetadataEntrySchema],
)
def batch_create_instrument_metadata(
    instrument_id: uuid.UUID,
    data: BatchMetadataCreate,
    db: Session = Depends(get_db),
):
    return metadata_service.batch_create_instrument_metadata(db, instrument_id, data)


@router.get(
    "/instruments/{instrument_id}/metadata/history",
    response_model=MetadataHistoryGrid,
)
def get_instrument_metadata_history(instrument_id: uuid.UUID, db: Session = Depends(get_db)):
    return metadata_service.get_instrument_metadata_history_grid(db, instrument_id)


@router.put(
    "/instruments/{instrument_id}/metadata/history/bulk",
    status_code=204,
)
def bulk_update_instrument_metadata_history(
    instrument_id: uuid.UUID,
    data: BulkHistoryUpdate,
    db: Session = Depends(get_db),
):
    metadata_service.bulk_update_instrument_metadata_history(db, instrument_id, data)
