import { OrderDetail } from './order.model';

export interface TradeLegSummary {
  id: string;
  instrument_id: string;
  instrument_name: string;
  direction: string;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  realized_pnl: number | null;
}

export interface TradeListItem {
  id: string;
  strategy_id: string;
  strategy_run_id: string | null;
  composite_id: string | null;
  strategy_name: string;
  is_paper: boolean;
  entry_at: string | null;
  exit_at: string | null;
  current_status: string | null;
  total_realized_pnl: number | null;
  total_unrealized_pnl: number | null;
  total_fees: number | null;
  legs: TradeLegSummary[];
  tags: string[];
  display_symbol: string;
}

export interface TradeCondition {
  id: string;
  condition_type: string;
  attribute_name: string;
  operator: string;
  threshold_value: number;
  is_met: boolean;
  met_at: string | null;
}

export interface TradeDataSeries {
  id: string;
  attribute_name: string;
  label: string | null;
  data_source: string;
}

export interface TradeSnapshot {
  attribute_name: string;
  snapshot_type: string;
  attribute_value: number;
  timestamp: string;
}

export interface TradeStatus {
  timestamp: string;
  status: string;
}

export interface TradeLegDetail extends TradeLegSummary {
  expected_entry_price: number | null;
  expected_exit_price: number | null;
  orders: OrderDetail[];
}

export interface TradeDetail extends TradeListItem {
  close_reason: string | null;
  parameters: any;
  legs: TradeLegDetail[];
  conditions: TradeCondition[];
  data_series: TradeDataSeries[];
  snapshots: TradeSnapshot[];
  statuses: TradeStatus[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  columns?: string[];
}
