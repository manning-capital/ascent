import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier


class ExchangeCreate(BaseModel):
    exchange_type_id: uuid.UUID
    name: Identifier
    display_name: str
    description: str | None = None
    provider_id: uuid.UUID | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool = True


class ExchangeUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    provider_id: uuid.UUID | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ExchangeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exchange_type_id: uuid.UUID
    exchange_type_name: str | None = None
    name: str
    display_name: str
    description: str | None = None
    provider_id: uuid.UUID | None = None
    provider_name: str | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
