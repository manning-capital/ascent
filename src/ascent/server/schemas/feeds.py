"""Pydantic schemas for feed API endpoints."""

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ascent.server.schemas.common import Identifier


class FeedListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    provider_id: uuid.UUID
    provider_name: str | None = None
    scope_type: Literal["instrument", "composite"]
    scope_type_id: uuid.UUID
    scope_type_name: str | None = None
    feed_ref: str
    output_table: str
    schedule: dict | None = None
    channel: str
    is_active: bool
    connection_status: str = "disconnected"
    total_runs: int = 0
    last_run_at: datetime.datetime | None = None
    last_run_status: str | None = None


class FeedDetail(FeedListItem):
    parameters: dict | list | str | int | float | bool | None = None
    parameter_schema: dict | None = None
    data_schema: dict | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


class FeedCreate(BaseModel):
    name: Identifier
    display_name: str
    provider_id: uuid.UUID
    scope_type: Literal["instrument", "composite"]
    scope_type_id: uuid.UUID
    feed_ref: str
    output_table: str
    description: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    parameter_schema: dict | None = None
    data_schema: dict | None = None
    schedule: dict | None = None
    channel: str
    is_active: bool = True


class FeedUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    provider_id: uuid.UUID | None = None
    scope_type: Literal["instrument", "composite"] | None = None
    scope_type_id: uuid.UUID | None = None
    parameters: dict | list | str | int | float | bool | None = None
    parameter_schema: dict | None = None
    data_schema: dict | None = None
    schedule: dict | None = None
    is_active: bool | None = None


class FeedRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_id: uuid.UUID
    partition_id: uuid.UUID | None = None
    partition_key: datetime.datetime | None = None
    status: str
    records_fetched: int | None = None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class StrategyFeedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: uuid.UUID
    feed_id: uuid.UUID
    is_required: bool
    order: int


class FeedPartitionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    partition_key: datetime.datetime
    window_start: datetime.datetime
    window_end: datetime.datetime
    status: str
    latest_run: FeedRunListItem | None = None


class FeedDependencyCreate(BaseModel):
    depends_on_feed_id: uuid.UUID


class FeedDependencySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feed_id: uuid.UUID
    depends_on_feed_id: uuid.UUID


class FeedPublishRequest(BaseModel):
    records: list[dict]
    partition_key: datetime.datetime | None = None


class FeedPublishResponse(BaseModel):
    feed_run_id: uuid.UUID
    partition_id: uuid.UUID | None = None
    partition_key: datetime.datetime | None = None
    records_count: int
    timestamp: str
