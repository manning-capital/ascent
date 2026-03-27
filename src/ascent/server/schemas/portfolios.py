import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class PortfolioCreate(BaseModel):
    name: str
    description: str | None = None
    base_currency_asset_id: uuid.UUID | None = None
    pricing_provider_id: uuid.UUID | None = None
    is_active: bool = True


class PortfolioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_currency_asset_id: uuid.UUID | None = None
    pricing_provider_id: uuid.UUID | None = None
    is_active: bool | None = None


class PortfolioSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    base_currency: str | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
