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
    recent_run_statuses: list[str] = []


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
    snapshot_timestamp: datetime.datetime
    status: str
    records_fetched: int | None = None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None


class FeedRunDetail(FeedRunListItem):
    """Single-run response that also exposes the persisted context snapshot."""

    context: dict | None = None


class StrategyFeedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: uuid.UUID
    feed_id: uuid.UUID
    is_required: bool
    order: int


class FeedDependencyCreate(BaseModel):
    depends_on_feed_id: uuid.UUID


class FeedDependencySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feed_id: uuid.UUID
    depends_on_feed_id: uuid.UUID


class FeedPublishRequest(BaseModel):
    records: list[dict]
    snapshot_timestamp: datetime.datetime | None = None


class FeedPublishResponse(BaseModel):
    feed_run_id: uuid.UUID
    snapshot_timestamp: datetime.datetime
    records_count: int
    timestamp: str


class FeedRunTradeItem(BaseModel):
    """A trade caused by a strategy run that consumed this feed run's output."""

    model_config = ConfigDict(from_attributes=True)

    trade_id: uuid.UUID
    strategy_id: uuid.UUID
    strategy_run_id: uuid.UUID
    status: str
    entry_at: datetime.datetime | None = None
    created_at: datetime.datetime


class TradeFeedRunItem(BaseModel):
    """A feed run consulted by the strategy run that created this trade."""

    model_config = ConfigDict(from_attributes=True)

    feed_run_id: uuid.UUID
    feed_id: uuid.UUID
    feed_name: str
    feed_display_name: str
    snapshot_timestamp: datetime.datetime
    status: str
    is_trigger: bool


class FeedRunUniverseInstrumentItem(BaseModel):
    """Instrument in a feed's universe at a specific snapshot timestamp."""

    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    name: str
    display_name: str
    instrument_type_id: uuid.UUID | None = None
    instrument_type_name: str | None = None
    added_at: datetime.datetime


class FeedRunUniverseCompositeItem(BaseModel):
    """Composite in a feed's universe at a specific snapshot timestamp."""

    model_config = ConfigDict(from_attributes=True)

    composite_id: uuid.UUID
    name: str
    display_name: str
    composite_type_id: uuid.UUID | None = None
    composite_type_name: str | None = None
    added_at: datetime.datetime


class UpstreamFeedRunItem(BaseModel):
    """A feed run that this run depended on (matched by snapshot_timestamp)."""

    model_config = ConfigDict(from_attributes=True)

    feed_run_id: uuid.UUID
    feed_id: uuid.UUID
    feed_name: str
    feed_display_name: str
    snapshot_timestamp: datetime.datetime
    status: str


class DownstreamStrategyRunItem(BaseModel):
    """A strategy run that consumed this feed run."""

    model_config = ConfigDict(from_attributes=True)

    strategy_run_id: uuid.UUID
    strategy_id: uuid.UUID
    strategy_name: str
    strategy_display_name: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    status: str
    is_trigger: bool


class FeedRunLineageResponse(BaseModel):
    """Combined upstream + downstream lineage for a feed run."""

    upstream_runs: list[UpstreamFeedRunItem]
    downstream_strategy_runs: list[DownstreamStrategyRunItem]
    downstream_trades: list[FeedRunTradeItem]
