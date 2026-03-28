import uuid

from pydantic import BaseModel, ConfigDict


class UniverseItemCreate(BaseModel):
    provider_id: uuid.UUID
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    provider_asset_group_id: uuid.UUID | None = None
    order: int


class UniverseItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: uuid.UUID
    provider_name: str | None = None
    from_asset_id: uuid.UUID
    from_asset_symbol: str | None = None
    to_asset_id: uuid.UUID
    to_asset_symbol: str | None = None
    provider_asset_group_id: uuid.UUID
    order: int
