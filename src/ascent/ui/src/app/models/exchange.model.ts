export interface ExchangeListItem {
  id: string;
  instrument_type_id: string | null;
  instrument_type_name: string | null;
  name: string;
  display_name: string;
  description: string | null;
  provider_id: string | null;
  provider_name: string | null;
  implementation_class: string | null;
  config: Record<string, any> | null;
  is_active: boolean;
  created_at: string | null;
}

export interface RecentOrderItem {
  id: string;
  timestamp: string;
  side: string;
  instrument_name: string | null;
  quantity: number;
  price: number;
  filled_quantity: number | null;
  average_fill_price: number | null;
  status: string | null;
}

export interface RecentTradeLegItem {
  id: string;
  trade_id: string;
  instrument_name: string | null;
  direction: string;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  realized_pnl: number | null;
  created_at: string;
}

export interface StrategyExchangeItem {
  exchange_id: string;
  exchange_name: string | null;
  exchange_display_name: string | null;
  provider_name: string | null;
  is_active: boolean;
  order: number;
}

export interface ExchangeStats {
  total_orders: number;
  orders_by_status: Record<string, number>;
  total_trade_legs: number;
  total_realized_pnl: number | null;
  total_volume: number | null;
  recent_orders: RecentOrderItem[];
  recent_trade_legs: RecentTradeLegItem[];
}
