from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier
from ascent.server.schemas.instruments import ProviderAssetLinkSchema
from ascent.server.schemas.metadata import MetadataEntrySchema


class AssetCreate(BaseModel):
    asset_type_id: uuid.UUID
    name: Identifier
    display_name: str
    description: str | None = None
    underlying_asset_id: uuid.UUID | None = None
    is_active: bool = True


class AssetUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    asset_type_id: uuid.UUID | None = None
    is_active: bool | None = None


class AssetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_type_id: uuid.UUID
    asset_type_name: str | None = None
    name: str
    display_name: str
    description: str | None = None
    underlying_asset_id: uuid.UUID | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None


class AssetDetailSchema(AssetSchema):
    metadata: list[MetadataEntrySchema] = []
    provider_links: list[ProviderAssetLinkSchema] = []
