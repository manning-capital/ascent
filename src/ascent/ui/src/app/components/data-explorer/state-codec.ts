import type { Cell, WorkspaceState, ChartCell, TableCell, Aggregation, Bucket, ChartCellKind } from './types';
import { EMPTY_WORKSPACE } from './types';

/** Encode the workspace state to a URL-safe base64 string for the `state`
 *  query param. Returns ``null`` for the empty workspace so the URL stays
 *  clean when nothing is configured yet. */
export function encodeWorkspace(state: WorkspaceState): string | null {
  if (isEmpty(state)) return null;
  try {
    const json = JSON.stringify(state);
    return btoa(unescape(encodeURIComponent(json)));
  } catch {
    return null;
  }
}

/** Decode a `state` query param. Returns ``null`` if the param is missing,
 *  malformed, or fails type validation. */
export function decodeWorkspace(raw: string | null): WorkspaceState | null {
  if (!raw) return null;
  let parsed: unknown;
  try {
    const json = decodeURIComponent(escape(atob(raw)));
    parsed = JSON.parse(json);
  } catch {
    return null;
  }
  return validateWorkspace(parsed);
}

/** Build a starter workspace from legacy query params. Used for back-compat
 *  with bookmarks predating the notebook redesign. */
export function legacyWorkspace(params: {
  table: string | null;
  start: string | null;
  end: string | null;
  entityIds: string[];
  descriptorIds: string[];
  periodIds: string[];
}): WorkspaceState {
  if (!params.table) return EMPTY_WORKSPACE;
  return {
    ...params,
    cells: [{ id: cellId(), kind: 'table' }],
  };
}

export function cellId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : 'c-' + Math.random().toString(36).slice(2, 11);
}

// ─── Validation ───────────────────────────────────────────────

const CHART_KINDS: ChartCellKind[] = ['line', 'bar', 'scatter', 'histogram'];
const AGGREGATIONS: Aggregation[] = ['mean', 'sum', 'min', 'max', 'count'];
const BUCKETS: Bucket[] = ['none', 'minute', 'hour', 'day', 'week', 'month'];

function validateWorkspace(raw: unknown): WorkspaceState | null {
  if (!isObj(raw)) return null;
  const cells = isArr(raw['cells']) ? raw['cells'].map(validateCell).filter((c): c is Cell => c !== null) : [];
  return {
    table: isStr(raw['table']) ? raw['table'] : null,
    start: isStr(raw['start']) ? raw['start'] : null,
    end: isStr(raw['end']) ? raw['end'] : null,
    entityIds: isStrArr(raw['entityIds']) ? raw['entityIds'] : [],
    descriptorIds: isStrArr(raw['descriptorIds']) ? raw['descriptorIds'] : [],
    periodIds: isStrArr(raw['periodIds']) ? raw['periodIds'] : [],
    cells,
  };
}

function validateCell(raw: unknown): Cell | null {
  if (!isObj(raw) || !isStr(raw['id']) || !isStr(raw['kind'])) return null;
  const kind = raw['kind'];
  if (kind === 'table') {
    return {
      id: raw['id'],
      kind: 'table',
      title: isStr(raw['title']) ? raw['title'] : undefined,
      height: typeof raw['height'] === 'number' ? raw['height'] : undefined,
    } satisfies TableCell;
  }
  if (CHART_KINDS.includes(kind as ChartCellKind)) {
    const series = isArr(raw['series'])
      ? raw['series'].map(validateSeries).filter((s) => s !== null)
      : [];
    return {
      id: raw['id'],
      kind: kind as ChartCellKind,
      title: isStr(raw['title']) ? raw['title'] : undefined,
      series: series as ChartCell['series'],
      bucket: BUCKETS.includes(raw['bucket'] as Bucket) ? (raw['bucket'] as Bucket) : undefined,
      height: typeof raw['height'] === 'number' ? raw['height'] : undefined,
    } satisfies ChartCell;
  }
  return null;
}

function validateSeries(raw: unknown) {
  if (!isObj(raw) || !isStr(raw['id']) || !isStr(raw['entityId']) || !isStr(raw['descriptorId'])) return null;
  return {
    id: raw['id'],
    entityId: raw['entityId'],
    descriptorId: raw['descriptorId'],
    periodId: isStr(raw['periodId']) ? raw['periodId'] : undefined,
    aggregation: AGGREGATIONS.includes(raw['aggregation'] as Aggregation) ? (raw['aggregation'] as Aggregation) : undefined,
    axis: raw['axis'] === 'right' ? ('right' as const) : raw['axis'] === 'left' ? ('left' as const) : undefined,
    label: isStr(raw['label']) ? raw['label'] : undefined,
  };
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}
function isArr(v: unknown): v is unknown[] {
  return Array.isArray(v);
}
function isStr(v: unknown): v is string {
  return typeof v === 'string';
}
function isStrArr(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === 'string');
}
function isEmpty(s: WorkspaceState): boolean {
  return s.table === null && s.cells.length === 0;
}
