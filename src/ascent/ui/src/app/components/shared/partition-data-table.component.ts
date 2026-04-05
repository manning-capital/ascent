import { Component, Input, Output, EventEmitter, inject, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, GridApi, GridReadyEvent, SortChangedEvent, ICellRendererParams } from 'ag-grid-community';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from './empty-state.component';
import { ThemeService } from '../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './data-table/ag-grid-theme';

/** Maps display column names to their ID column and route prefix. */
const LINK_COLUMNS: Record<string, { idCol: string; route: string }> = {
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
const KEY_COLUMNS = new Set(['timestamp']);

/** Columns that contain datetime values and should be formatted. */
const DATE_COLUMNS = new Set(['timestamp']);

/** Columns that are raw IDs and should be hidden from the table. */
const HIDDEN_COLUMNS = new Set([
  'provider_id', 'from_asset_id', 'to_asset_id', 'asset_id', 'period_id',
  'instrument_id', 'composite_id', 'attribute_id', 'metadata_id',
]);

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

@Component({
  selector: 'app-partition-data-table',
  standalone: true,
  imports: [AgGridAngular, EmptyStateComponent, Skeleton],
  styles: [`
    :host { display: flex; flex-direction: column; min-height: 0; }
  `],
  template: `
    @if (data.length === 0 && !isLoading) {
      <div class="flex items-center justify-center flex-1">
        <app-empty-state title="No partition data" message="This partition has no data rows yet." icon="data"/>
      </div>
    } @else if (isLoading && data.length === 0) {
      <div class="flex-1 flex flex-col min-h-0">
        <div class="flex gap-3 px-3 py-2.5 border-b border-edge">
          @for (_ of [1,2,3,4,5]; track $index) {
            <p-skeleton height="1rem" class="flex-1"/>
          }
        </div>
        <div class="flex-1 flex flex-col overflow-hidden">
          @for (_ of skeletonRows; track $index) {
            <div class="flex gap-3 px-3 py-2.5 border-b border-edge-dim">
              @for (_ of [1,2,3,4,5]; track $index) {
                <p-skeleton height="0.875rem" class="flex-1"/>
              }
            </div>
          }
        </div>
        <div class="shrink-0 flex items-center justify-between px-3 py-2 border-t border-edge">
          <p-skeleton width="10rem" height="1.25rem"/>
          <div class="flex gap-1.5">
            @for (_ of [1,2,3]; track $index) {
              <p-skeleton width="2rem" height="2rem" borderRadius="6px"/>
            }
          </div>
          <p-skeleton width="8rem" height="1.25rem"/>
        </div>
      </div>
    } @else {
      <div class="flex-1 overflow-y-auto min-h-0 transition-opacity duration-200 rounded-lg border border-edge overflow-clip"
           [class.opacity-40]="isLoading" [class.pointer-events-none]="isLoading"
           [attr.data-ag-theme-mode]="themeMode()">
        <ag-grid-angular
          [theme]="theme"
          [rowData]="data"
          [columnDefs]="agColumns()"
          [defaultColDef]="defaultColDef"
          [domLayout]="'autoHeight'"
          [suppressCellFocus]="true"
          (gridReady)="onGridReady($event)"
          (sortChanged)="onSortChanged($event)"/>
      </div>

      <div class="shrink-0 flex items-center justify-between px-3 py-2 border-t border-edge text-xs text-fg-muted">
        <div class="flex items-center gap-2">
          <span>Rows per page:</span>
          <select [value]="pageSize" (change)="onPageSizeSelect($event)" class="bg-transparent border border-edge rounded px-1 py-0.5 text-xs text-fg cursor-pointer">
            <option [value]="25">25</option>
            <option [value]="50">50</option>
            <option [value]="100">100</option>
          </select>
        </div>
        <span>{{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, total) }} of {{ total }}</span>
        <div class="flex gap-1">
          <button (click)="goToPage(page - 1)" [disabled]="page <= 1" class="px-2 py-1 rounded border border-edge hover:bg-elevated disabled:opacity-30 disabled:cursor-not-allowed">&lsaquo;</button>
          <button (click)="goToPage(page + 1)" [disabled]="page >= totalPages" class="px-2 py-1 rounded border border-edge hover:bg-elevated disabled:opacity-30 disabled:cursor-not-allowed">&rsaquo;</button>
        </div>
      </div>
    }
  `,
})
export class PartitionDataTableComponent {
  @Input() data: Record<string, any>[] = [];
  @Input() total = 0;
  @Input() page = 1;
  @Input() pageSize = 25;
  @Input() totalPages = 0;
  @Input() loading = false;
  @Input() sortField: string = 'timestamp';
  @Input() sortOrder: number = -1;  // -1 = desc, 1 = asc
  skeletonRows = Array.from({ length: 20 });
  Math = Math;
  @Output() pageChange = new EventEmitter<number>();
  @Output() pageSizeChange = new EventEmitter<number>();
  @Output() sortChange = new EventEmitter<{ field: string; order: number }>();

  private router = inject(Router);
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;
  private gridApi: GridApi | null = null;
  private datePipe = new DatePipe('en-US');

  defaultColDef: ColDef = {
    sortable: true,
    resizable: false,
    suppressMovable: true,
    flex: 1,
    cellStyle: { fontFamily: 'monospace', whiteSpace: 'nowrap' },
  };

  /** True when the parent loading flag is set. */
  get isLoading(): boolean {
    return this.loading;
  }

  /** Visible columns — filters out raw ID columns. */
  get columns(): string[] {
    if (this.data.length === 0) return [];
    return Object.keys(this.data[0]).filter(col => !HIDDEN_COLUMNS.has(col));
  }

  agColumns = computed<ColDef[]>(() => {
    // Trigger recompute when data changes
    const data = this.data;
    if (data.length === 0) return [];

    const cols = Object.keys(data[0]).filter(col => !HIDDEN_COLUMNS.has(col));
    return cols.map(col => {
      const isKey = KEY_COLUMNS.has(col) || this.isLinkColumn(col);
      const isLink = this.isLinkColumn(col);

      const def: ColDef = {
        headerName: this.formatHeader(col),
        field: col,
        sort: col === this.sortField ? (this.sortOrder === -1 ? 'desc' : 'asc') : undefined,
      };

      if (isKey) {
        def.cellStyle = {
          fontFamily: 'monospace',
          whiteSpace: 'nowrap',
          background: 'color-mix(in srgb, var(--fg) 4%, transparent)',
        };
        def.headerClass = 'key-col-header';
      }

      if (isLink) {
        def.cellRenderer = PartitionLinkCellRenderer;
        def.cellRendererParams = { colField: col, router: this.router };
      }

      if (DATE_COLUMNS.has(col)) {
        def.valueFormatter = (params) => {
          if (!params.value) return '';
          return this.datePipe.transform(params.value, 'MMM d, yyyy HH:mm:ss') ?? String(params.value);
        };
      }

      return def;
    });
  });

  /** Format a column key into a capitalized header label. */
  formatHeader(col: string): string {
    return col
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  /** Whether this column should render as a link. */
  isLinkColumn(col: string): boolean {
    const cfg = LINK_COLUMNS[col];
    if (!cfg) return false;
    return this.data.length > 0 && this.data[0][cfg.idCol] !== undefined;
  }

  onGridReady(event: GridReadyEvent): void {
    this.gridApi = event.api;
  }

  onSortChanged(event: SortChangedEvent): void {
    const sortModel = event.api.getColumnState().find(c => c.sort);
    if (sortModel) {
      const field = sortModel.colId;
      const order = sortModel.sort === 'desc' ? -1 : 1;
      if (field !== this.sortField || order !== this.sortOrder) {
        this.sortChange.emit({ field, order });
      }
    }
  }

  goToPage(newPage: number): void {
    if (newPage >= 1 && newPage <= this.totalPages) {
      this.pageChange.emit(newPage);
    }
  }

  onPageSizeSelect(event: Event): void {
    const val = +(event.target as HTMLSelectElement).value;
    if (val !== this.pageSize) {
      this.pageSizeChange.emit(val);
    }
  }
}
