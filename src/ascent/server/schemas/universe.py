import uuid

from pydantic import BaseModel, ConfigDict


class UniverseItemCreate(BaseModel):
    instrument_id: uuid.UUID
    order: int


class UniverseBatchAddInstruments(BaseModel):
    instrument_ids: list[uuid.UUID]
    start_order: int = 1


class UniverseItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    instrument_name: str | None = None
    instrument_display_name: str | None = None
    instrument_type_id: uuid.UUID | None = None
    is_active: bool = True
    order: int


class CompositeUniverseItemCreate(BaseModel):
    composite_id: uuid.UUID
    order: int


class CompositeUniverseBatchAdd(BaseModel):
    composite_ids: list[uuid.UUID]
    start_order: int = 1


class CompositeUniverseItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    composite_id: uuid.UUID
    composite_name: str | None = None
    composite_display_name: str | None = None
    composite_type_id: uuid.UUID | None = None
    is_active: bool = True
    order: int
