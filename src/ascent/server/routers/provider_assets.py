import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ascent.server.dependencies import get_db
from ascent.server.schemas.metadata import MetadataEntryCreate, MetadataEntrySchema
from ascent.server.schemas.provider_assets import (
    AssetGroupCreate,
    AssetGroupMemberCreate,
    AssetGroupSchema,
    AssetGroupUpdate,
    ProviderAssetLinkCreate,
    ProviderAssetLinkSchema,
)
from ascent.server.services import metadata_service, provider_asset_service

router = APIRouter(tags=["provider-assets"])


# ---------------------------------------------------------------------------
# Provider-Asset Links
# ---------------------------------------------------------------------------


@router.get("/provider-assets", response_model=list[ProviderAssetLinkSchema])
def list_provider_asset_links(
    provider_id: uuid.UUID | None = Query(None),
    asset_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
):
    return provider_asset_service.get_provider_asset_links(db, provider_id, asset_id)


@router.post("/provider-assets", status_code=201, response_model=ProviderAssetLinkSchema)
def create_provider_asset_link(data: ProviderAssetLinkCreate, db: Session = Depends(get_db)):
    return provider_asset_service.create_provider_asset_link(db, data)


@router.delete("/provider-assets/{provider_id}/{asset_id}", status_code=204)
def delete_provider_asset_link(
    provider_id: uuid.UUID, asset_id: uuid.UUID, db: Session = Depends(get_db)
):
    provider_asset_service.delete_provider_asset_link(db, provider_id, asset_id)


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


# ---------------------------------------------------------------------------
# Asset Groups
# ---------------------------------------------------------------------------


@router.get("/asset-groups", response_model=list[AssetGroupSchema])
def list_asset_groups(
    min_members: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    return provider_asset_service.get_asset_groups(db, min_members=min_members)


@router.get("/asset-groups/{group_id}", response_model=AssetGroupSchema)
def get_asset_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    return provider_asset_service.get_asset_group(db, group_id)


@router.post("/asset-groups", status_code=201)
def create_asset_group(data: AssetGroupCreate, db: Session = Depends(get_db)):
    return provider_asset_service.create_asset_group(db, data)


@router.put("/asset-groups/{group_id}")
def update_asset_group(group_id: uuid.UUID, data: AssetGroupUpdate, db: Session = Depends(get_db)):
    return provider_asset_service.update_asset_group(db, group_id, data)


@router.delete("/asset-groups/{group_id}", status_code=204)
def delete_asset_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    provider_asset_service.delete_asset_group(db, group_id)


@router.post("/asset-groups/{group_id}/members", status_code=201)
def add_group_member(
    group_id: uuid.UUID, data: AssetGroupMemberCreate, db: Session = Depends(get_db)
):
    return provider_asset_service.add_group_member(db, group_id, data)


@router.delete(
    "/asset-groups/{group_id}/members/{provider_id}/{from_asset_id}/{to_asset_id}",
    status_code=204,
)
def remove_group_member(
    group_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    provider_asset_service.remove_group_member(
        db, group_id, provider_id, from_asset_id, to_asset_id
    )
