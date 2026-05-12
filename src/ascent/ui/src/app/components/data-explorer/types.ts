/** Workspace state for the Data Explorer notebook.
 *
 * Each cell is a chart or a table. Cells stack vertically; the workspace
 * filter context (table, time range) applies to all of them. The whole state
 * round-trips through a single base64-encoded `state` query param.
 */

export type ChartCellKind = 'line' | 'bar' | 'scatter' | 'histogram';
export type TableCellKind = 'table';
export type CellKind = ChartCellKind | TableCellKind;

export type Aggregation = 'mean' | 'sum' | 'min' | 'max' | 'count';
export type Bucket = 'none' | 'minute' | 'hour' | 'day' | 'week' | 'month';

export interface SeriesSpec {
  /** Stable local id for color/legend continuity across edits. */
  id: string;
  entityId: string;
  descriptorId: string;
  periodId?: string;
  aggregation?: Aggregation;
  /** Y-axis side for line/bar dual-axis layouts. */
  axis?: 'left' | 'right';
  /** User override for the legend label. */
  label?: string;
}

export interface ChartCell {
  id: string;
  kind: ChartCellKind;
  title?: string;
  series: SeriesSpec[];
  /** Time-bucket size for line/bar cells. */
  bucket?: Bucket;
  /** User-resized cell height in px (default 320). */
  height?: number;
}

export interface TableCell {
  id: string;
  kind: TableCellKind;
  title?: string;
  height?: number;
}

export type Cell = ChartCell | TableCell;

export interface WorkspaceState {
  table: string | null;
  start: string | null;       // ISO 8601
  end: string | null;
  /** Workspace-wide entity filter — applies to the table cell and is the
   * default available pool for chart series chips. */
  entityIds: string[];
  /** Workspace-wide descriptor filter — same role. */
  descriptorIds: string[];
  /** Workspace-wide period filter (only meaningful for has_period sources). */
  periodIds: string[];
  cells: Cell[];
}

export const EMPTY_WORKSPACE: WorkspaceState = {
  table: null,
  start: null,
  end: null,
  entityIds: [],
  descriptorIds: [],
  periodIds: [],
  cells: [],
};
