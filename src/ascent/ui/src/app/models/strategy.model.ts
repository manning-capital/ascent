export interface StrategyListItem {
  id: string;
  name: string;
  description: string | null;
  strategy_type: string;
  strategy_class: string;
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
