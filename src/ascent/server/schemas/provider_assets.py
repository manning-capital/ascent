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


class AssetGroupCreate(BaseModel):
    is_active: bool = True
    members: list["AssetGroupMemberCreate"] = []


class AssetGroupMemberCreate(BaseModel):
    provider_id: uuid.UUID
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    order: int


class AssetGroupUpdate(BaseModel):
    is_active: bool | None = None


class AssetGroupMemberSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_asset_group_id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str | None = None
    from_asset_id: uuid.UUID
    from_asset_symbol: str | None = None
    to_asset_id: uuid.UUID
    to_asset_symbol: str | None = None
    order: int


class AssetGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool = True
    members: list[AssetGroupMemberSchema] = []
    created_at: datetime.datetime | None = None
