import uuid

from pydantic import BaseModel, ConfigDict


class TypeCreate(BaseModel):
    symbol: str | None = None
    name: str
    description: str | None = None
    parent_type_id: uuid.UUID | None = None


class TypeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    parent_type_id: uuid.UUID | None = None


class TypeItemWithSymbol(TypeItem):
    symbol: str


class TypeHierarchyItem(TypeItem):
    children: list["TypeHierarchyItem"] = []


TypeHierarchyItem.model_rebuild()
