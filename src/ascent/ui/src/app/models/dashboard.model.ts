export interface CumulativePnlPoint {
  date: string;
  value: number;
  symbol: string;
}

export interface DashboardStats {
  // Counts
  total_strategies: number;
  active_strategies: number;
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  wins: number;
  losses: number;
  breakeven: number;

  // P&L
  total_pnl: number;
  today_pnl: number;
  total_unrealized_pnl: number;
  total_fees: number;
  net_pnl: number;
  avg_trade_pnl: number;
  median_pnl: number;
  avg_win: number;
  avg_loss: number;
  max_win: number;
  max_loss: number;

  // Risk
  win_rate: number;
  profit_factor: number;
  payoff_ratio: number;
  expectancy: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  max_drawdown_duration: number;

  // Distribution
  std_dev_pnl: number;
  skewness: number;
  kurtosis: number;

  // Streaks
  max_win_streak: number;
  max_loss_streak: number;

  // Holding periods (seconds)
  avg_holding_seconds: number | null;
  avg_holding_wins_seconds: number | null;
  avg_holding_losses_seconds: number | null;

  // Chart data
  cumulative_pnl: CumulativePnlPoint[];
}
