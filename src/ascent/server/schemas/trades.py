import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.orders import OrderDetailSchema


class TradeLegSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    instrument_name: str
    direction: str
    quantity: float
    entry_price: float | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None


class TradeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    strategy_name: str
    is_paper: bool
    entry_at: datetime.datetime | None = None
    exit_at: datetime.datetime | None = None
    current_status: str | None = None
    total_realized_pnl: float | None = None
    total_unrealized_pnl: float | None = None
    total_fees: float | None = None
    legs: list[TradeLegSummary] = []
    tags: list[str] = []
    display_symbol: str = ""


class TradeConditionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_type: str
    attribute_name: str
    operator: str
    threshold_value: float
    is_met: bool = False
    met_at: datetime.datetime | None = None


class TradeDataSeriesSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attribute_name: str
    label: str | None = None
    data_source: str


class TradeSnapshotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribute_name: str
    snapshot_type: str
    attribute_value: float
    timestamp: datetime.datetime


class TradeStatusSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime.datetime
    status: str


class TradeLegDetail(TradeLegSummary):
    expected_entry_price: float | None = None
    expected_exit_price: float | None = None
    orders: list[OrderDetailSchema] = []


class TradeLegCreate(BaseModel):
    instrument_id: uuid.UUID
    direction: str
    quantity: float
    exchange_id: uuid.UUID | None = None
    expected_entry_price: float | None = None
    entry_price: float | None = None
    expected_exit_price: float | None = None
    exit_price: float | None = None


class TradeLegUpdate(BaseModel):
    direction: str | None = None
    quantity: float | None = None
    expected_entry_price: float | None = None
    entry_price: float | None = None
    expected_exit_price: float | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None


class TradeCreate(BaseModel):
    strategy_id: uuid.UUID
    portfolio_id: uuid.UUID
    is_paper: bool = False
    entry_at: datetime.datetime | None = None
    parameters: dict | list | str | int | float | bool | None = None
    legs: list[TradeLegCreate] = []


class TradeUpdate(BaseModel):
    is_paper: bool | None = None
    entry_at: datetime.datetime | None = None
    exit_at: datetime.datetime | None = None
    close_reason: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    total_realized_pnl: float | None = None
    total_unrealized_pnl: float | None = None
    total_fees: float | None = None


class TradeStatusCreate(BaseModel):
    trade_status_type_id: uuid.UUID
    timestamp: datetime.datetime | None = None


class TradeConditionCreate(BaseModel):
    condition_type: str
    attribute_id: uuid.UUID
    operator: str
    threshold_value: float
    is_met: bool = False
    met_at: datetime.datetime | None = None
    instrument_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    from_asset_id: uuid.UUID | None = None
    to_asset_id: uuid.UUID | None = None
    period_id: uuid.UUID | None = None


class TradeSnapshotCreate(BaseModel):
    attribute_id: uuid.UUID
    snapshot_type: str
    attribute_value: float
    timestamp: datetime.datetime
    instrument_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None


class TradeDataSeriesCreate(BaseModel):
    attribute_id: uuid.UUID
    label: str | None = None
    data_source: str
    instrument_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None
    period_id: uuid.UUID | None = None


class TradeDetail(TradeListItem):
    close_reason: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    legs: list[TradeLegDetail] = []
    conditions: list[TradeConditionSchema] = []
    data_series: list[TradeDataSeriesSchema] = []
    snapshots: list[TradeSnapshotSchema] = []
    statuses: list[TradeStatusSchema] = []
