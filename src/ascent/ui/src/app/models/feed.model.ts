import { JsonSchema } from './strategy.model';

export interface FeedListItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  provider_id: string;
  provider_name: string | null;
  scope_type: 'instrument' | 'composite';
  scope_type_id: string;
  scope_type_name: string | null;
  feed_ref: string;
  output_table: string;
  schedule: Record<string, any> | null;
  channel: string;
  is_active: boolean;
  total_runs: number;
  last_run_at: string | null;
  last_run_status: string | null;
  recent_run_statuses: string[];
}

export interface FeedDetail extends FeedListItem {
  parameters: any;
  parameter_schema: JsonSchema | null;
  data_schema: Record<string, any> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FeedRunListItem {
  id: string;
  feed_id: string;
  snapshot_timestamp: string;
  status: string;
  records_fetched: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface FeedRunContextAttribute {
  id: string;
  name: string;
  display_name?: string | null;
  period?: { id: string; name: string; duration_nanoseconds?: number | null } | null;
}

export interface FeedRunContextSource {
  table: string;
  scope_type: string;
  attributes: FeedRunContextAttribute[];
}

export interface FeedRunContext {
  snapshot_timestamp?: string;
  sources: FeedRunContextSource[];
}

export interface FeedRunDetail extends FeedRunListItem {
  context: FeedRunContext | null;
}

export interface RunDataResponse {
  items: Record<string, any>[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FeedRunTradeItem {
  trade_id: string;
  strategy_id: string;
  strategy_run_id: string;
  status: string;
  entry_at: string | null;
  created_at: string;
}

export interface TradeFeedRunItem {
  feed_run_id: string;
  feed_id: string;
  feed_name: string;
  feed_display_name: string;
  snapshot_timestamp: string;
  status: string;
  is_trigger: boolean;
}

export interface StrategyFeedNode {
  id: string;
  name: string;
  description: string | null;
  feed_ref: string;
  is_active: boolean;
  schedule: Record<string, any> | null;
  channel: string;
  is_required: boolean;
  order: number;
  depends_on: string[];
  last_run_status: string | null;
  last_run_at: string | null;
}

export interface StrategyFeedDAG {
  nodes: StrategyFeedNode[];
  edges: [string, string][]; // [from_feed_id, to_feed_id]
}

export interface StrategyRunFeedRunItem {
  feed_id: string;
  feed_run_id: string;
  is_trigger: boolean;
  status: string;
}

export interface StrategyRunListItem {
  id: string;
  strategy_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  feed_runs: StrategyRunFeedRunItem[];
  trigger_feed_id: string | null;
}

export interface FeedRunUniverseInstrumentItem {
  instrument_id: string;
  name: string;
  display_name: string;
  instrument_type_id: string | null;
  instrument_type_name: string | null;
  added_at: string;
}

export interface FeedRunUniverseCompositeItem {
  composite_id: string;
  name: string;
  display_name: string;
  composite_type_id: string | null;
  composite_type_name: string | null;
  added_at: string;
}

export interface UpstreamFeedRunItem {
  feed_run_id: string;
  feed_id: string;
  feed_name: string;
  feed_display_name: string;
  snapshot_timestamp: string;
  status: string;
}

export interface DownstreamStrategyRunItem {
  strategy_run_id: string;
  strategy_id: string;
  strategy_name: string;
  strategy_display_name: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  is_trigger: boolean;
}

export interface FeedRunLineageResponse {
  upstream_runs: UpstreamFeedRunItem[];
  downstream_strategy_runs: DownstreamStrategyRunItem[];
  downstream_trades: FeedRunTradeItem[];
}
