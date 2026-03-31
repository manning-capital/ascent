import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier


class TypeCreate(BaseModel):
    name: Identifier
    display_name: str
    description: str | None = None
    parent_type_id: uuid.UUID | None = None


class TypeUpdate(BaseModel):
    parent_type_id: uuid.UUID | None = None
    remove_metadata_ids: list[uuid.UUID] = []
    remove_provider_asset_metadata_ids: list[uuid.UUID] = []


class TypePatch(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None


class CompositeTypePatch(TypePatch):
    min_members: int | None = None
    max_members: int | None = None


class MetadataConflict(BaseModel):
    metadata_id: uuid.UUID
    metadata_name: str
    metadata_display_name: str
    value_type: str
    child_is_required: bool
    parent_is_required: bool
    parent_source_type_name: str


class ReparentPreview(BaseModel):
    child_id: uuid.UUID
    child_name: str
    new_parent_id: uuid.UUID
    new_parent_name: str
    child_own_fields: list = []
    parent_effective_fields: list = []
    conflicts: list[MetadataConflict] = []
    child_own_provider_asset_fields: list | None = None
    parent_effective_provider_asset_fields: list | None = None
    provider_asset_conflicts: list[MetadataConflict] | None = None


class TypeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    parent_type_id: uuid.UUID | None = None


class TypeHierarchyItem(TypeItem):
    children: list["TypeHierarchyItem"] = []


TypeHierarchyItem.model_rebuild()


class InstrumentTypeCreate(TypeCreate):
    pass


class InstrumentTypeItem(TypeItem):
    pass


class InstrumentTypeHierarchyItem(InstrumentTypeItem):
    children: list["InstrumentTypeHierarchyItem"] = []


InstrumentTypeHierarchyItem.model_rebuild()


class CompositeTypeCreate(TypeCreate):
    min_members: int = 2
    max_members: int = 2


class CompositeTypeItem(TypeItem):
    min_members: int = 2
    max_members: int = 2


class CompositeTypeHierarchyItem(CompositeTypeItem):
    children: list["CompositeTypeHierarchyItem"] = []


CompositeTypeHierarchyItem.model_rebuild()
