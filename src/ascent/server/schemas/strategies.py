import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class StrategyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    strategy_type: str
    strategy_class: str
    parameters: dict | list | str | int | float | bool | None = None
    portfolio_id: uuid.UUID
    is_active: bool
    # Computed stats
    total_trades: int = 0
    open_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    last_trade_at: datetime.datetime | None = None


class StrategyCreate(BaseModel):
    name: str
    strategy_type_id: uuid.UUID
    strategy_class: str
    portfolio_id: uuid.UUID
    description: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    is_active: bool = True


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    strategy_class: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    is_active: bool | None = None


class StrategyDetail(StrategyListItem):
    portfolio_name: str | None = None
    parameter_schema: dict | None = None
    created_at: datetime.datetime | None = None


class StrategyFeedNode(BaseModel):
    """A feed node in the strategy's feed dependency DAG."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    feed_ref: str
    is_active: bool
    schedule: dict | None = None
    channel: str
    is_required: bool
    order: int
    depends_on: list[uuid.UUID] = []
    last_run_status: str | None = None
    last_run_at: datetime.datetime | None = None


class StrategyFeedDAG(BaseModel):
    """The full feed dependency graph for a strategy."""

    nodes: list[StrategyFeedNode]
    edges: list[tuple[uuid.UUID, uuid.UUID]]  # (from_feed_id, to_feed_id) dependency edges


class StrategyRunFeedRunItem(BaseModel):
    """A feed run that was active during a strategy run."""

    model_config = ConfigDict(from_attributes=True)

    feed_id: uuid.UUID
    feed_run_id: uuid.UUID
    is_trigger: bool
    status: str


class StrategyRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    status: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error_message: str | None = None
    feed_runs: list[StrategyRunFeedRunItem] = []
    trigger_feed_id: uuid.UUID | None = None
