export interface StrategyListItem {
  id: string;
  name: string;
  description: string | null;
  strategy_type: string;
  strategy_ref: string;
  parameters: any;
  portfolio_id: string;
  is_active: boolean;
  total_trades: number;
  open_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  last_trade_at: string | null;
}

export interface StrategyDetail extends StrategyListItem {
  portfolio_name: string | null;
  parameter_schema: JsonSchema | null;
  created_at: string | null;
}

export interface StrategyStats {
  // Core
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: number;

  // PnL
  total_pnl: number;
  total_fees: number;
  net_pnl: number;
  avg_trade_pnl: number;
  median_pnl: number;
  avg_win: number;
  avg_loss: number;
  max_win: number;
  max_loss: number;

  // Risk
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
  cumulative_pnl: { date: string; value: number; symbol: string }[];
  pnl_distribution: { center: number; count: number }[];
}

/** Subset of JSON Schema that Pydantic v2 generates. */
export interface JsonSchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: any;
  enum?: any[];
  anyOf?: { type?: string; enum?: any[] }[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
}

export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
}
