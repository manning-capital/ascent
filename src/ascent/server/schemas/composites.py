import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class CompositeMemberCreate(BaseModel):
    instrument_id: uuid.UUID
    order: int


class CompositeMemberSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    composite_id: uuid.UUID
    instrument_id: uuid.UUID
    instrument_name: str | None = None
    instrument_display_name: str | None = None
    order: int


class CompositeCreate(BaseModel):
    name: str
    display_name: str
    composite_type_id: uuid.UUID
    description: str | None = None
    is_active: bool = True
    members: list[CompositeMemberCreate] = []


class CompositeUpdate(BaseModel):
    composite_type_id: uuid.UUID | None = None
    is_active: bool | None = None


class CompositeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    composite_type_id: uuid.UUID
    description: str | None = None
    is_active: bool = True
    members: list[CompositeMemberSchema] = []
    created_at: datetime.datetime | None = None
