import type { Signal } from '@angular/core';

export type CellType =
  | 'text'
  | 'monospace'
  | 'link'
  | 'status'
  | 'tag'
  | 'currency'
  | 'date'
  | 'number'
  | 'custom';

export type FilterType = 'text' | 'select' | 'none';

export interface DataTableColumn<T = any> {
  field: string;
  header: string;
  cellType?: CellType;
  filterType?: FilterType;
  sortable?: boolean;
  width?: number;
  minWidth?: number;

  // Link cells
  linkRoute?: (row: T) => string | any[] | null;

  // Tag/status cells
  tagMapper?: (value: any, row: T) => { label: string; severity: string };

  // Filter options (for 'select' filterType)
  filterOptions?: any[] | Signal<any[]>;

  // Formatting
  valueFormatter?: (params: any) => string;
  cellClass?: string | ((params: any) => string);

  // Custom escape hatch
  cellRenderer?: any;
  cellRendererParams?: any;
  valueGetter?: (params: any) => any;
}
