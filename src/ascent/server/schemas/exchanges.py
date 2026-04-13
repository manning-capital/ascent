import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier


class ExchangeCreate(BaseModel):
    instrument_type_id: uuid.UUID | None = None
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
    instrument_type_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ExchangeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_type_id: uuid.UUID | None = None
    instrument_type_name: str | None = None
    name: str
    display_name: str
    description: str | None = None
    provider_id: uuid.UUID | None = None
    provider_name: str | None = None
    implementation_class: str | None = None
    config: dict | None = None
    is_active: bool = True
    created_at: datetime.datetime | None = None


class RecentOrderItem(BaseModel):
    id: uuid.UUID
    timestamp: datetime.datetime
    side: str
    instrument_name: str | None = None
    quantity: float
    price: float
    filled_quantity: float | None = None
    average_fill_price: float | None = None
    status: str | None = None


class RecentTradeLegItem(BaseModel):
    id: uuid.UUID
    trade_id: uuid.UUID
    instrument_name: str | None = None
    direction: str
    quantity: float
    entry_price: float | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None
    created_at: datetime.datetime


class ExchangeStats(BaseModel):
    """Aggregate statistics for an exchange."""

    total_orders: int = 0
    orders_by_status: dict[str, int] = {}
    total_trade_legs: int = 0
    total_realized_pnl: float | None = None
    total_volume: float | None = None
    recent_orders: list[RecentOrderItem] = []
    recent_trade_legs: list[RecentTradeLegItem] = []
