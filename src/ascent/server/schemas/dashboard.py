from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_strategies: int = 0
    active_strategies: int = 0
    total_trades: int = 0
    open_trades: int = 0
    total_pnl: float = 0.0
    today_pnl: float = 0.0
    win_rate: float = 0.0
