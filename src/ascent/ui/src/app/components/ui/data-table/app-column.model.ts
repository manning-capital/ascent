import type { Signal, TemplateRef } from '@angular/core';
import type { Observable } from 'rxjs';

/** Server-side fetch shape. Mirrors the existing ServerFetchFn contract so
 * existing entity services keep working. */
export type AppFetchFn<T = any> = (
  page: number,
  pageSize: number,
  sort?: { field: string; order: 'asc' | 'desc' },
) => Observable<{ items: T[]; total: number; columns?: string[] }>;

export type AppCellType =
  | 'text'
  | 'monospace'
  | 'link'
  | 'tag'
  | 'status'
  | 'currency'
  | 'date'
  | 'number'
  | 'template';

export type AppFilterType =
  | 'text'
  | 'select'
  | 'multiselect'
  | 'date'
  | 'number'
  | 'none';

export type AppSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast';

export interface AppFilterOption {
  label: string;
  value: any;
}

export interface AppColumn<T = any> {
  field: string;
  header: string;

  cellType?: AppCellType;
  cellTemplate?: TemplateRef<{ $implicit: T }>;
  cellClass?: string | ((row: T) => string);

  /** Format the displayed value for built-in cell types. */
  format?: (value: any, row: T) => string;

  /** For cellType === 'link' — produces a router link (string or array). */
  linkRoute?: (row: T) => string | any[] | null;

  /** For cellType === 'tag' / 'status' — derives label + severity from value. */
  tagMapper?: (value: any, row: T) => { label: string; severity: AppSeverity };

  sortable?: boolean;
  filter?: AppFilterType;
  filterOptions?: AppFilterOption[] | Signal<AppFilterOption[]>;

  width?: number;
  minWidth?: number;

  pinned?: 'left' | 'right';

  /** Default visibility — users may toggle this in the column-visibility menu. */
  visible?: boolean;
  /** When false, column is excluded from CSV export. Defaults to true. */
  exportable?: boolean;
}

export interface AppColumnState {
  visible: Record<string, boolean>;
  order: string[];
  widths: Record<string, number>;
}
