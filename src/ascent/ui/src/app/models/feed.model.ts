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
  partition_id: string | null;
  partition_key: string | null;
  status: string;
  records_fetched: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface FeedPartitionItem {
  id: string | null;
  partition_key: string;
  window_start: string;
  window_end: string;
  status: string;
  latest_run: FeedRunListItem | null;
}

export interface PartitionDataResponse {
  items: Record<string, any>[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
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
