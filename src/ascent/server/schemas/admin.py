import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class FeedPartitionCreate(BaseModel):
    feed_id: uuid.UUID
    partition_key: datetime.datetime
    window_start: datetime.datetime
    window_end: datetime.datetime
    status: str = "PENDING"


class FeedPartitionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_id: uuid.UUID
    partition_key: datetime.datetime
    window_start: datetime.datetime
    window_end: datetime.datetime
    status: str


class FeedRunCreate(BaseModel):
    feed_id: uuid.UUID
    partition_id: uuid.UUID | None = None
    status: str
    records_fetched: int | None = None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class FeedRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_id: uuid.UUID
    partition_id: uuid.UUID | None = None
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


class PAGAEntry(BaseModel):
    timestamp: datetime.datetime
    provider_asset_group_id: uuid.UUID
    attribute_id: uuid.UUID
    attribute_value: float


class PAGABatchCreate(BaseModel):
    entries: list[PAGAEntry]
