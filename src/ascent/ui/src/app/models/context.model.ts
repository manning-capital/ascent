// Mirror of the backend `ContextResponse` shape from
// `ascent.server.schemas.context`. Same Pydantic shape on both sides — the
// UI never drifts from what the engine wrote to `FeedRun.context`.

export type ScopeType = 'instrument' | 'composite';

export type AttributeTable =
  | 'instrument_attribute'
  | 'instrument_period_attribute'
  | 'composite_attribute'
  | 'composite_period_attribute';

export interface Period {
  id: string;
  name: string;
  duration_nanoseconds: number | null;
}

export interface Attribute {
  id: string;
  name: string;
  display_name: string | null;
  period: Period | null;
}

export interface ContextSource {
  table: AttributeTable;
  scope_type: ScopeType;
  attributes: Attribute[];
}

export interface Context {
  snapshot_timestamp: string;
  sources: ContextSource[];
}

export interface SeriesPoint {
  t: string;
  v: number;
}

export interface SeriesScopeRef {
  type: ScopeType;
  id: string;
  name: string | null;
  display_name: string | null;
}

export interface ContextSeries {
  name: string;
  display_name: string;
  attribute: Attribute;
  period: Period | null;
  scope: SeriesScopeRef;
  source_table: AttributeTable;
  source_feed_run_ids: string[];
  points: SeriesPoint[];
}

export interface TradeView {
  series: string[];
  series_labels: Record<string, string>;
  show_trade_markers: boolean;
}

export interface ContextResponse {
  context: Context;
  series: ContextSeries[];
  trade_view: TradeView | null;
}
