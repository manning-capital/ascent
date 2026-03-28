import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class ExchangeCreate(BaseModel):
    exchange_type_id: uuid.UUID
    name: str
    description: str | None = None
    provider_id: uuid.UUID | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool = True


class ExchangeUpdate(BaseModel):
    name: str | None = None
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
    description: str | None = None
    provider_id: uuid.UUID | None = None
    provider_name: str | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None
