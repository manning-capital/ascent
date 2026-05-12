import type { AppColumn } from './app-column.model';

/**
 * Auto-column helpers for partition-style result tables (Data Explorer,
 * Feed Run data view, etc.) where the API returns rows keyed by attribute
 * names rather than a fixed schema.
 */

/** Display columns that resolve to navigable entity links via their `*_id` sibling. */
export const LINK_COLUMNS: Record<string, { idCol: string; route: string }> = {
  provider: { idCol: 'provider_id', route: '/settings/master-data/providers' },
  from_asset: { idCol: 'from_asset_id', route: '/settings/master-data/assets' },
  to_asset: { idCol: 'to_asset_id', route: '/settings/master-data/assets' },
  asset: { idCol: 'asset_id', route: '/settings/master-data/assets' },
  instrument: { idCol: 'instrument_id', route: '/settings/master-data/instruments' },
  composite: { idCol: 'composite_id', route: '/settings/master-data/composites' },
  attribute: { idCol: 'attribute_id', route: '/settings/types/attributes' },
  metadata: { idCol: 'metadata_id', route: '/settings/types/metadata-types' },
};

/** Columns that should be visually highlighted as key/identifier columns. */
export const KEY_COLUMNS = new Set(['timestamp']);

/** Columns containing datetime values; rendered with date formatting. */
export const DATE_COLUMNS = new Set(['timestamp']);

/** Raw `*_id` columns that should be hidden — the corresponding display column links to them. */
export const HIDDEN_COLUMNS = new Set([
  'provider_id', 'from_asset_id', 'to_asset_id', 'asset_id', 'period_id',
  'instrument_id', 'composite_id', 'attribute_id', 'metadata_id',
]);

export function formatHeader(col: string): string {
  return col
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function isLinkColumn(col: string, sample: Record<string, any> | undefined): boolean {
  const cfg = LINK_COLUMNS[col];
  if (!cfg) return false;
  return !!sample && sample[cfg.idCol] !== undefined;
}

export interface AutoColumnOptions {
  /** Honor LINK_COLUMNS detection. */
  withLinks?: boolean;
  /** Explicit column ordering from the server (overrides Object.keys order). */
  serverColumns?: string[] | null;
}

/**
 * Build an AppColumn list from a sample row + options. Hidden columns are
 * dropped, link-eligible columns are tagged with `cellType: 'link'`, key
 * columns get monospace styling, date columns get date cellType.
 */
export function generateAutoColumns<T extends Record<string, any>>(
  sample: T | undefined,
  options: AutoColumnOptions = {},
): AppColumn<T>[] {
  if (!sample && !options.serverColumns?.length) return [];
  const fields = options.serverColumns?.length
    ? options.serverColumns
    : Object.keys(sample ?? {});

  const visible = fields.filter((f) => !HIDDEN_COLUMNS.has(f));

  return visible.map<AppColumn<T>>((field) => {
    const isKey = KEY_COLUMNS.has(field);
    const isDate = DATE_COLUMNS.has(field);
    const linkCfg = options.withLinks ? LINK_COLUMNS[field] : undefined;
    const linkable = linkCfg && sample?.[linkCfg.idCol] !== undefined;

    if (linkable && linkCfg) {
      return {
        field,
        header: formatHeader(field),
        cellType: 'link',
        linkRoute: (row: any) =>
          row?.[linkCfg.idCol] != null ? [linkCfg.route, row[linkCfg.idCol]] : null,
        sortable: false,
        cellClass: 'font-mono',
      };
    }

    return {
      field,
      header: formatHeader(field),
      cellType: isDate ? 'date' : isKey ? 'monospace' : 'text',
      cellClass: isKey ? 'font-mono' : undefined,
      sortable: false,
    };
  });
}
