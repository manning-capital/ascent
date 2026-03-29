import datetime
import enum
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class MetadataValueType(str, enum.Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"


# Allowed types for metadata values (primitives + date/time types, no dicts/lists)
PrimitiveValue = str | int | float | bool | datetime.date | datetime.time | datetime.datetime | None

_ALLOWED_TYPES = (str, int, float, bool, datetime.date, datetime.time, datetime.datetime)


def _validate_primitive(v: Any) -> PrimitiveValue:
    if v is not None and not isinstance(v, _ALLOWED_TYPES):
        raise ValueError(
            f"Metadata values must be primitives (str, int, float, bool, date, time, datetime), got {type(v).__name__}"
        )
    return v


class MetadataEntryCreate(BaseModel):
    metadata_id: uuid.UUID
    value: Any
    timestamp: datetime.datetime | None = None

    @field_validator("value")
    @classmethod
    def value_must_be_primitive(cls, v: Any) -> PrimitiveValue:
        return _validate_primitive(v)


class MetadataEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str = ""
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

    @field_validator("value")
    @classmethod
    def value_must_be_primitive(cls, v: Any) -> PrimitiveValue:
        return _validate_primitive(v)


class MetadataTypeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str = ""
    description: str | None = None
    value_type: str = "string"
    is_active: bool = True


class MetadataTypeCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    value_type: MetadataValueType = MetadataValueType.STRING


class MetadataTypeUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    value_type: MetadataValueType | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Generic entity usage (reusable across all entity types)
# ---------------------------------------------------------------------------


class EntityUsageItem(BaseModel):
    label: str
    count: int
    kind: str = "cascade"  # "cascade" = will be deleted, "reference" = linkage will break


class EntityUsage(BaseModel):
    items: list[EntityUsageItem]
    total: int


class AssetTypeMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str = ""
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
    metadata_display_name: str = ""
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
    metadata_display_name: str = ""
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

    @field_validator("value")
    @classmethod
    def value_must_be_primitive(cls, v: Any) -> PrimitiveValue:
        return _validate_primitive(v)


class BatchMetadataCreate(BaseModel):
    timestamp: datetime.datetime
    entries: list[BatchMetadataEntry]


# ---------------------------------------------------------------------------
# Metadata history grid
# ---------------------------------------------------------------------------


class MetadataFieldInfo(BaseModel):
    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str = ""
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

    @field_validator("value")
    @classmethod
    def value_must_be_primitive(cls, v: Any) -> PrimitiveValue:
        return _validate_primitive(v)


class BulkHistoryInsertEntry(BaseModel):
    timestamp: datetime.datetime
    metadata_id: uuid.UUID
    value: Any

    @field_validator("value")
    @classmethod
    def value_must_be_primitive(cls, v: Any) -> PrimitiveValue:
        return _validate_primitive(v)


class BulkHistoryDeleteEntry(BaseModel):
    timestamp: datetime.datetime
    metadata_id: uuid.UUID | None = None


class BulkHistoryUpdate(BaseModel):
    updates: list[BulkHistoryUpdateEntry] = []
    inserts: list[BulkHistoryInsertEntry] = []
    deletes: list[BulkHistoryDeleteEntry] = []
