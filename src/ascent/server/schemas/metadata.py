import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class MetadataEntryCreate(BaseModel):
    metadata_id: uuid.UUID
    value: Any
    timestamp: datetime.datetime | None = None


class MetadataEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    value: Any
    timestamp: datetime.datetime


class MetadataHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime.datetime
    value: Any
    created_at: datetime.datetime | None = None


class MetadataHistoryUpdate(BaseModel):
    value: Any | None = None
    timestamp: datetime.datetime | None = None


class MetadataTypeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    value_type: str = "string"
    is_active: bool = True


class MetadataTypeCreate(BaseModel):
    name: str
    description: str | None = None
    value_type: str = "string"


class AssetTypeMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_description: str | None = None
    value_type: str
    is_required: bool
    display_order: int


class AssetTypeMetadataCreate(BaseModel):
    metadata_id: uuid.UUID
    is_required: bool = True
    display_order: int = 0


class ProviderTypeMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_description: str | None = None
    value_type: str
    is_required: bool
    display_order: int


class ProviderTypeMetadataCreate(BaseModel):
    metadata_id: uuid.UUID
    is_required: bool = True
    display_order: int = 0
