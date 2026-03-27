import uuid

from pydantic import BaseModel, ConfigDict


class TypeCreate(BaseModel):
    symbol: str
    name: str
    description: str | None = None


class TypeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class TypeItemWithSymbol(TypeItem):
    symbol: str
