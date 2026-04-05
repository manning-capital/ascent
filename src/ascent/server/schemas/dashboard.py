from pydantic import BaseModel

from ascent.server.schemas.strategies import CumulativePnlPoint


class DashboardStats(BaseModel):
    # Counts
    total_strategies: int = 0
    active_strategies: int = 0
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0

    # P&L
    total_pnl: float = 0.0
    today_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    net_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    median_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0

    # Risk
    win_rate: float = 0.0
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
