import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class FeedRunCreate(BaseModel):
    feed_id: uuid.UUID
    snapshot_timestamp: datetime.datetime
    status: str
    records_fetched: int | None = None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class FeedRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_id: uuid.UUID
    snapshot_timestamp: datetime.datetime
    status: str
    records_fetched: int | None = None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class StrategyRunCreate(BaseModel):
    strategy_id: uuid.UUID
    status: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class StrategyRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    status: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class StrategyRunFeedRunCreate(BaseModel):
    strategy_run_id: uuid.UUID
    feed_run_id: uuid.UUID
    feed_id: uuid.UUID
    is_trigger: bool = False


class StrategyRunFeedRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_run_id: uuid.UUID
    feed_run_id: uuid.UUID
    feed_id: uuid.UUID
    is_trigger: bool


class InstrumentAttributeEntry(BaseModel):
    timestamp: datetime.datetime
    instrument_id: uuid.UUID
    attribute_id: uuid.UUID
    attribute_value: float


class InstrumentAttributeBatchCreate(BaseModel):
    entries: list[InstrumentAttributeEntry]


class CompositeAttributeEntry(BaseModel):
    timestamp: datetime.datetime
    composite_id: uuid.UUID
    attribute_id: uuid.UUID
    attribute_value: float


class CompositeAttributeBatchCreate(BaseModel):
    entries: list[CompositeAttributeEntry]
