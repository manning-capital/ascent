from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier
from ascent.server.schemas.instruments import ProviderAssetLinkSchema
from ascent.server.schemas.metadata import MetadataEntrySchema


class ProviderCreate(BaseModel):
    provider_type_id: uuid.UUID
    name: Identifier
    display_name: str
    description: str | None = None
    provider_external_code: str | None = None
    underlying_provider_id: uuid.UUID | None = None
    url: str | None = None
    image_url: str | None = None
    is_active: bool = True


class ProviderUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    provider_external_code: str | None = None
    url: str | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ProviderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_type_id: uuid.UUID
    provider_type_name: str | None = None
    name: str
    display_name: str
    description: str | None = None
    provider_external_code: str | None = None
    underlying_provider_id: uuid.UUID | None = None
    url: str | None = None
    image_url: str | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None


class ProviderDetailSchema(ProviderSchema):
    metadata: list[MetadataEntrySchema] = []
    asset_links: list[ProviderAssetLinkSchema] = []
