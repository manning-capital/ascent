import { Component } from '@angular/core';
import { Router } from '@angular/router';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ICellRendererParams } from 'ag-grid-community';

/** Maps display column names to their ID column and route prefix. */
export const LINK_COLUMNS: Record<string, { idCol: string; route: string }> = {
  provider: { idCol: 'provider_id', route: '/settings/providers' },
  from_asset: { idCol: 'from_asset_id', route: '/settings/assets' },
  to_asset: { idCol: 'to_asset_id', route: '/settings/assets' },
  asset: { idCol: 'asset_id', route: '/settings/assets' },
  instrument: { idCol: 'instrument_id', route: '/settings/instruments' },
  composite: { idCol: 'composite_id', route: '/settings/composites' },
  attribute: { idCol: 'attribute_id', route: '/settings/attributes' },
  metadata: { idCol: 'metadata_id', route: '/settings/metadata-types' },
};

/** Columns that should be visually highlighted as key/identifier columns. */
export const KEY_COLUMNS = new Set(['timestamp']);

/** Columns that contain datetime values and should be formatted. */
export const DATE_COLUMNS = new Set(['timestamp']);

/** Columns that are raw IDs and should be hidden from the table. */
export const HIDDEN_COLUMNS = new Set([
  'provider_id', 'from_asset_id', 'to_asset_id', 'asset_id', 'period_id',
  'instrument_id', 'composite_id', 'attribute_id', 'metadata_id',
]);

/** Formats a snake_case column name into a Title Case header. */
export function formatHeader(col: string): string {
  return col.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

/** Checks whether a column should be rendered as a navigable link. */
export function isLinkColumn(col: string, data: Record<string, any>[]): boolean {
  const cfg = LINK_COLUMNS[col];
  if (!cfg) return false;
  return data.length > 0 && data[0][cfg.idCol] !== undefined;
}

// ─── Link cell renderer for partition data ──────────────────
@Component({
  selector: 'ag-partition-link-cell',
  standalone: true,
  template: `
    @if (isLink) {
      <a (click)="navigate($event)" class="text-primary hover:underline cursor-pointer">{{ text }}</a>
    } @else {
      {{ text }}
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%;font-family:monospace;white-space:nowrap' },
})
export class PartitionLinkCellRenderer implements ICellRendererAngularComp {
  text = '';
  isLink = false;
  private route = '';
  private id = '';
  private router?: Router;

  agInit(params: ICellRendererParams & { colField?: string; router?: Router }): void {
    this.router = params.router;
    this.update(params);
  }

  refresh(params: ICellRendererParams & { colField?: string; router?: Router }): boolean {
    this.update(params);
    return true;
  }

  navigate(e: Event): void {
    e.stopPropagation();
    if (this.router && this.route && this.id) {
      this.router.navigate([this.route, this.id]);
    }
  }

  private update(params: ICellRendererParams & { colField?: string }): void {
    const col = params.colField ?? '';
    this.text = params.value ?? '-';
    const cfg = LINK_COLUMNS[col];
    if (cfg && params.data?.[cfg.idCol] !== undefined) {
      this.isLink = true;
      this.route = cfg.route;
      this.id = params.data[cfg.idCol];
    } else {
      this.isLink = false;
    }
  }
}
