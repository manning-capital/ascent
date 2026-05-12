import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    timestamp: datetime.datetime
    order_type_id: uuid.UUID
    side: str
    exchange_id: uuid.UUID
    instrument_id: uuid.UUID
    quantity: float
    price: float
    time_in_force: str | None = None
    trade_leg_id: uuid.UUID | None = None


class OrderUpdate(BaseModel):
    filled_quantity: float | None = None
    average_fill_price: float | None = None
    external_order_id: str | None = None
    time_in_force: str | None = None


class OrderStatusCreate(BaseModel):
    order_status_type_id: uuid.UUID
    timestamp: datetime.datetime | None = None
    error_message: str | None = None
    error_code: str | None = None


class OrderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime.datetime
    order_type: str
    side: str
    instrument_id: uuid.UUID
    instrument_name: str
    quantity: float
    price: float
    filled_quantity: float | None = None
    average_fill_price: float | None = None
    external_order_id: str | None = None
    time_in_force: str | None = None
    current_status: str | None = None
    exchange_name: str | None = None


class OrderStatusSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime.datetime
    status: str
    error_message: str | None = None
    error_code: str | None = None


class OrderDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime.datetime
    order_type: str
    side: str
    instrument_id: uuid.UUID
    instrument_name: str
    quantity: float
    price: float
    filled_quantity: float | None = None
    average_fill_price: float | None = None
    external_order_id: str | None = None
    time_in_force: str | None = None
    current_status: str | None = None
    exchange_name: str | None = None
    statuses: list[OrderStatusSchema] = []
