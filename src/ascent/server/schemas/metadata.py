import datetime
import enum
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class MetadataValueType(str, enum.Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"


class MetadataEntryCreate(BaseModel):
    metadata_id: uuid.UUID
    value: Any
    timestamp: datetime.datetime | None = None


class MetadataEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
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
    display_name: str
    description: str | None = None
    value_type: MetadataValueType = MetadataValueType.STRING
    is_active: bool = True


class MetadataTypeCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    value_type: MetadataValueType = MetadataValueType.STRING


class AssetTypeMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
    metadata_description: str | None = None
    value_type: str
    is_required: bool
    display_order: int
    is_inherited: bool = False
    source_type_id: uuid.UUID | None = None
    source_type_name: str | None = None


class AssetTypeMetadataCreate(BaseModel):
    metadata_id: uuid.UUID
    is_required: bool = True
    display_order: int = 0


class AssetTypeProviderAssetMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
    metadata_description: str | None = None
    value_type: str
    is_required: bool
    display_order: int
    is_inherited: bool = False
    source_type_id: uuid.UUID | None = None
    source_type_name: str | None = None


class AssetTypeProviderAssetMetadataCreate(BaseModel):
    metadata_id: uuid.UUID
    is_required: bool = True
    display_order: int = 0


class ProviderTypeMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
    metadata_description: str | None = None
    value_type: str
    is_required: bool
    display_order: int
    is_inherited: bool = False
    source_type_id: uuid.UUID | None = None
    source_type_name: str | None = None


class ProviderTypeMetadataCreate(BaseModel):
    metadata_id: uuid.UUID
    is_required: bool = True
    display_order: int = 0


# ---------------------------------------------------------------------------
# Batch metadata create
# ---------------------------------------------------------------------------


class BatchMetadataEntry(BaseModel):
    metadata_id: uuid.UUID
    value: Any


class BatchMetadataCreate(BaseModel):
    timestamp: datetime.datetime
    entries: list[BatchMetadataEntry]


# ---------------------------------------------------------------------------
# Metadata history grid
# ---------------------------------------------------------------------------


class MetadataFieldInfo(BaseModel):
    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
    value_type: str


class MetadataSnapshotRow(BaseModel):
    timestamp: datetime.datetime
    values: dict[str, Any]


class MetadataHistoryGrid(BaseModel):
    fields: list[MetadataFieldInfo]
    snapshots: list[MetadataSnapshotRow]


# ---------------------------------------------------------------------------
# Bulk history update
# ---------------------------------------------------------------------------


class BulkHistoryUpdateEntry(BaseModel):
    old_timestamp: datetime.datetime
    new_timestamp: datetime.datetime | None = None
    metadata_id: uuid.UUID
    value: Any


class BulkHistoryInsertEntry(BaseModel):
    timestamp: datetime.datetime
    metadata_id: uuid.UUID
    value: Any


class BulkHistoryDeleteEntry(BaseModel):
    timestamp: datetime.datetime
    metadata_id: uuid.UUID | None = None


class BulkHistoryUpdate(BaseModel):
    updates: list[BulkHistoryUpdateEntry] = []
    inserts: list[BulkHistoryInsertEntry] = []
    deletes: list[BulkHistoryDeleteEntry] = []
