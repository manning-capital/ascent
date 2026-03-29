import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class StrategyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    strategy_type: str
    strategy_ref: str
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
    strategy_ref: str
    portfolio_id: uuid.UUID
    description: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    parameter_schema: dict | None = None
    is_active: bool = True


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    strategy_ref: str | None = None
    parameters: dict | list | str | int | float | bool | None = None
    is_active: bool | None = None


class StrategyDetail(StrategyListItem):
    portfolio_name: str | None = None
    parameter_schema: dict | None = None
    created_at: datetime.datetime | None = None


class CumulativePnlPoint(BaseModel):
    date: str
    value: float
    symbol: str


class PnlDistributionBin(BaseModel):
    center: float
    count: int


class StrategyStats(BaseModel):
    """Comprehensive trade statistics for a strategy, computed server-side."""

    # Core
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0

    # PnL
    total_pnl: float = 0.0
    total_fees: float = 0.0
    net_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    median_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0

    # Risk
    profit_factor: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # Distribution
    std_dev_pnl: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    # Streaks
    max_win_streak: int = 0
    max_loss_streak: int = 0

    # Holding periods (seconds)
    avg_holding_seconds: float | None = None
    avg_holding_wins_seconds: float | None = None
    avg_holding_losses_seconds: float | None = None

    # Chart data
    cumulative_pnl: list[CumulativePnlPoint] = []
    pnl_distribution: list[PnlDistributionBin] = []


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


class StrategyFeedCreate(BaseModel):
    feed_id: uuid.UUID
    is_required: bool = True
    order: int = 0


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
