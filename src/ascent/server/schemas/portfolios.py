import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier


class PortfolioCreate(BaseModel):
    name: Identifier
    display_name: str
    description: str | None = None
    base_currency_asset_id: uuid.UUID | None = None
    pricing_provider_id: uuid.UUID | None = None
    is_active: bool = True


class PortfolioUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    base_currency_asset_id: uuid.UUID | None = None
    pricing_provider_id: uuid.UUID | None = None
    is_active: bool | None = None


class PortfolioSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    base_currency: str | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
