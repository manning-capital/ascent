import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class AttributeCreate(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True


class AttributeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AttributeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
