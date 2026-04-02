import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class ProviderAssetLinkCreate(BaseModel):
    provider_id: uuid.UUID
    asset_id: uuid.UUID
    identifier: str


class ProviderAssetLinkSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: uuid.UUID
    provider_name: str | None = None
    asset_id: uuid.UUID
    asset_name: str | None = None
    asset_symbol: str | None = None
    identifier: str
    created_at: datetime.datetime | None = None


class InstrumentCreate(BaseModel):
    name: str
    display_name: str
    instrument_type_id: uuid.UUID
    provider_id: uuid.UUID
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    description: str | None = None
    is_active: bool = True


class InstrumentUpdate(BaseModel):
    instrument_type_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    from_asset_id: uuid.UUID | None = None
    to_asset_id: uuid.UUID | None = None
    is_active: bool | None = None


class InstrumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    instrument_type_id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str | None = None
    from_asset_id: uuid.UUID
    from_asset_name: str | None = None
    to_asset_id: uuid.UUID
    to_asset_name: str | None = None
    description: str | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
