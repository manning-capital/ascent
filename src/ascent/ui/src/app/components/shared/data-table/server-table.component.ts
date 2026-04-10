import {
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  isSignal,
} from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AgGridAngular } from 'ag-grid-angular';
import type {
  ColDef,
  GridApi,
  GridReadyEvent,
  RowClickedEvent,
  SortChangedEvent,
} from 'ag-grid-community';
import { Paginator } from 'primeng/paginator';
import { Skeleton } from 'primeng/skeleton';
import { ThemeService } from '../../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './ag-grid-theme';
import type { DataTableColumn, ServerFetchFn } from './data-table.model';
import {
  StatusCellRenderer,
  TagCellRenderer,
  LinkCellRenderer,
  CurrencyCellRenderer,
} from './cell-renderers';
import { SelectFloatingFilter, MultiSelectFloatingFilter } from './floating-filters';
import {
  HIDDEN_COLUMNS,
  KEY_COLUMNS,
  DATE_COLUMNS,
  LINK_COLUMNS,
  PartitionLinkCellRenderer,
  formatHeader,
  isLinkColumn,
} from './partition-columns';

@Component({
  selector: 'app-server-table',
  standalone: true,
  imports: [AgGridAngular, Paginator, Skeleton],
  styles: [`
    :host { display: flex; flex-direction: column; min-height: 0; }
    :host ::ng-deep .ag-row.cursor-pointer { cursor: pointer; }
    :host ::ng-deep .ag-header-cell:last-child .ag-header-cell-resize { display: none; }
  `],
  template: `
    @if (_initialLoad() && _rowData().length === 0) {
      <div [class]="showPaginator() ? 'flex-1 flex flex-col min-h-0 rounded-lg border border-edge overflow-clip' : 'rounded-lg border border-edge overflow-clip'">
        <div class="flex gap-3 px-4 border-b border-edge shrink-0" style="height:48px;align-items:center">
          @for (_ of _skeletonCols(); track $index) { <p-skeleton height="0.75rem" class="flex-1"/> }
        </div>
        <div [class]="showPaginator() ? 'flex-1 overflow-hidden' : ''">
          @for (_ of showPaginator() ? skeletonRows : skeletonRowsSmall; track $index) {
            <div class="flex gap-3 px-4 border-b border-edge" style="height:42px;align-items:center">
              @for (_ of _skeletonCols(); track $index) { <p-skeleton height="1rem" class="flex-1"/> }
            </div>
          }
        </div>
      </div>
      @if (showPaginator()) {
        <div class="mt-4 shrink-0 flex items-center justify-center gap-1 px-4 py-2">
          <p-skeleton width="10rem" height="0.875rem"/>
          @for (_ of [1,2]; track $index) { <p-skeleton width="2.5rem" height="2.5rem" borderRadius="50%"/> }
          @for (_ of [1,2,3]; track $index) { <p-skeleton width="2.5rem" height="2.5rem" borderRadius="50%"/> }
          @for (_ of [1,2]; track $index) { <p-skeleton width="2.5rem" height="2.5rem" borderRadius="50%"/> }
          <p-skeleton width="4rem" height="2.5rem" borderRadius="6px"/>
        </div>
      }
    } @else {
      <div class="rounded-lg overflow-clip border border-edge transition-opacity duration-200"
           [style.flex]="showPaginator() ? '1' : null"
           [style.min-height]="showPaginator() ? '0' : null"
           [class.opacity-40]="_loading()" [class.pointer-events-none]="_loading()"
           [attr.data-ag-theme-mode]="themeMode()">
        <ag-grid-angular
          [theme]="theme"
          [rowData]="_rowData()"
          [columnDefs]="agColumnDefs()"
          [defaultColDef]="agDefaultColDef()"
          [domLayout]="showPaginator() ? 'normal' : 'autoHeight'"
          style="width: 100%; height: 100%"
          [pagination]="false"
          [rowHeight]="rowHeight() ?? undefined"
          [headerHeight]="headerHeight() ?? undefined"
          [suppressCellFocus]="true"
          [overlayNoRowsTemplate]="noRowsHtml()"
          [rowClass]="rowClickRoute() ? 'cursor-pointer' : ''"
          (gridReady)="onGridReady($event)"
          (sortChanged)="onSortChanged($event)"
          (rowClicked)="onRowClicked($event)"/>
      </div>
      @if (showPaginator() && (!_loading() || _total() > 0)) {
        <p-paginator class="mt-4 shrink-0"
          [rows]="_pageSize()"
          [totalRecords]="_total()"
          [rowsPerPageOptions]="pageSizeOptions()"
          [first]="_first()"
          [showCurrentPageReport]="true"
          currentPageReportTemplate="Showing {first} to {last} of {totalRecords}"
          (onPageChange)="onServerPageChange($event)"/>
      }
    }
  `,
})
export class ServerTableComponent<T = any> {
  // ─── Column definition — provide ONE of: ─────────────────
  /** Declarative column config (converted via toColDef). */
  columns = input<DataTableColumn<T>[]>([]);
  /** Pre-built AG Grid ColDef array (used as-is). */
  columnDefs = input<ColDef[]>([]);
  /** Auto-generate columns from data keys (partition-style). */
  autoColumns = input(false);
  /** Enable partition-style link detection in auto-columns mode. */
  autoLinks = input(false);

  // ─── Data fetching ────────────────────────────────────────
  fetchPage = input<ServerFetchFn<T> | null>(null);

  // ─── Pagination ───────────────────────────────────────────
  pageSize = input(25);
  pageSizeOptions = input<number[]>([25, 50, 100]);
  showPaginator = input(true);

  // ─── Behavior ─────────────────────────────────────────────
  rowClickRoute = input<((row: T) => string | any[]) | null>(null);
  emptyMessage = input('No data found.');
  rowHeight = input<number | undefined>(undefined);
  headerHeight = input<number | undefined>(undefined);

  // ─── Outputs ──────────────────────────────────────────────
  sortChange = output<{ field: string; order: string }>();
  pageChange = output<number>();
  pageSizeChange = output<number>();
  rowClick = output<T>();
  dataLoaded = output<T[]>();

  // ─── Internal state ───────────────────────────────────────
  _rowData = signal<T[]>([]);
  _total = signal(0);
  _first = signal(0);
  _pageSize = signal(25);
  _loading = signal(false);
  _initialLoad = signal(true);
  _sort = signal<{ field: string; order: string } | undefined>(undefined);

  // ─── Services & utilities ─────────────────────────────────
  private router = inject(Router);
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;
  gridApi: GridApi | null = null;

  private datePipe = new DatePipe('en-US');
  skeletonRows = Array.from({ length: 50 });
  skeletonRowsSmall = Array.from({ length: 5 });
  _skeletonCols = computed(() => {
    const cols = this.columns();
    if (cols.length > 0) return Array.from({ length: cols.length });
    const defs = this.columnDefs();
    if (defs.length > 0) return Array.from({ length: defs.length });
    return Array.from({ length: 5 });
  });

  // ─── Computed: no-rows overlay ────────────────────────────
  noRowsHtml = computed(() =>
    `<span style="font-size: 12px; opacity: 0.5;">${this.emptyMessage()}</span>`,
  );

  // ─── Computed: default column def ─────────────────────────
  agDefaultColDef = computed<ColDef>(() => {
    const hasFilters = this.columns().some(c => c.filterType && c.filterType !== 'none');
    return {
      sortable: true,
      resizable: false,
      suppressMovable: true,
      floatingFilter: hasFilters,
      flex: 1,
      comparator: () => 0,
    };
  });

  // ─── Computed: resolved column defs ───────────────────────
  agColumnDefs = computed<ColDef[]>(() => {
    // Priority 1: pre-built ColDef[]
    const defs = this.columnDefs();
    if (defs.length > 0) return defs;

    // Priority 2: declarative DataTableColumn config
    const cols = this.columns();
    if (cols.length > 0) return cols.map(col => this.toColDef(col));

    // Priority 3: auto-generate from data keys
    if (this.autoColumns()) return this.buildAutoColumns();

    return [];
  });

  // ─── Constructor effect: reload on fetchPage / pageSize change ─
  constructor() {
    effect(() => {
      const fn = this.fetchPage();
      const ps = this.pageSize();
      if (fn) {
        untracked(() => {
          this._pageSize.set(ps);
          this._first.set(0);
          this._loadPage(fn);
        });
      }
    });
  }

  // ─── Server-side page loading ─────────────────────────────
  private _loadPage(fn?: ServerFetchFn<T>): void {
    const fetchFn = fn ?? this.fetchPage();
    if (!fetchFn) return;
    const page = Math.floor(this._first() / this._pageSize()) + 1;
    this._loading.set(true);
    fetchFn(page, this._pageSize(), this._sort()).subscribe({
      next: (res) => {
        this._rowData.set(res.items);
        this._total.set(res.total);
        this._loading.set(false);
        this._initialLoad.set(false);
        this.dataLoaded.emit(res.items);
      },
      error: () => {
        this._loading.set(false);
        this._initialLoad.set(false);
      },
    });
  }

  // ─── Event handlers ───────────────────────────────────────
  onGridReady(event: GridReadyEvent): void {
    this.gridApi = event.api;
  }

  onSortChanged(event: SortChangedEvent): void {
    const sortModel = event.api.getColumnState().find(c => c.sort);
    if (sortModel) {
      const sort = { field: sortModel.colId, order: sortModel.sort ?? 'asc' };
      this._sort.set(sort);
      this._first.set(0);
      this.sortChange.emit(sort);
      this._loadPage();
    }
  }

  onServerPageChange(event: { first?: number; rows?: number }): void {
    if (event.first != null) this._first.set(event.first);
    if (event.rows != null && event.rows !== this._pageSize()) {
      this._pageSize.set(event.rows);
      this.pageSizeChange.emit(event.rows);
    }
    const page = Math.floor(this._first() / this._pageSize()) + 1;
    this.pageChange.emit(page);
    this._loadPage();
  }

  onRowClicked(event: RowClickedEvent): void {
    const route = this.rowClickRoute();
    if (route && event.data) {
      const target = route(event.data);
      if (Array.isArray(target)) {
        this.router.navigate(target);
      } else {
        this.router.navigate([target]);
      }
    }
    this.rowClick.emit(event.data);
  }

  // ─── Column conversion: DataTableColumn → ColDef ──────────
  private toColDef(col: DataTableColumn<T>): ColDef {
    const def: ColDef = {
      headerName: col.header,
      field: col.field,
      sortable: col.sortable ?? true,
      minWidth: col.minWidth,
    };

    if (col.width) {
      def.minWidth = col.width;
    }

    // Cell type handling
    switch (col.cellType) {
      case 'monospace':
        def.cellClass = 'font-mono text-surface-500';
        break;

      case 'link':
        def.cellRenderer = LinkCellRenderer;
        def.cellRendererParams = { linkRoute: col.linkRoute };
        break;

      case 'status':
        def.cellRenderer = StatusCellRenderer;
        if (col.tagMapper) {
          def.cellRendererParams = { tagMapper: col.tagMapper };
        }
        break;

      case 'tag':
        def.cellRenderer = TagCellRenderer;
        if (col.tagMapper) {
          def.cellRendererParams = { tagMapper: col.tagMapper };
        }
        break;

      case 'currency':
        def.cellRenderer = CurrencyCellRenderer;
        break;

      case 'date':
        def.valueFormatter = (params) => {
          if (!params.value) return '';
          return this.datePipe.transform(params.value, 'MMM d, yyyy HH:mm:ss') ?? String(params.value);
        };
        break;

      case 'number':
        if (col.valueFormatter) {
          def.valueFormatter = col.valueFormatter;
        }
        break;

      case 'custom':
        if (col.cellRenderer) def.cellRenderer = col.cellRenderer;
        if (col.cellRendererParams) def.cellRendererParams = col.cellRendererParams;
        break;
    }

    // Override with explicit valueFormatter/valueGetter/cellClass if provided
    if (col.valueFormatter && col.cellType !== 'number') {
      def.valueFormatter = col.valueFormatter;
    }
    if (col.valueGetter) def.valueGetter = col.valueGetter;
    if (col.cellClass) {
      def.cellClass = col.cellClass;
    }

    // Filter handling
    this.applyFilter(def, col);

    return def;
  }

  private applyFilter(def: ColDef, col: DataTableColumn<T>): void {
    switch (col.filterType) {
      case 'text':
        def.filter = 'agTextColumnFilter';
        def.floatingFilter = true;
        def.filterParams = {
          filterOptions: ['contains'],
          suppressAndOrCondition: true,
          debounceMs: 200,
        };
        def.floatingFilterComponentParams = {
          suppressFilterButton: true,
        };
        break;

      case 'select': {
        const options = this.resolveFilterOptions(col);
        const isBoolean = options.length > 0 && typeof options[0]?.value === 'boolean';
        const isMulti = !isBoolean && options.length > 0 && typeof options[0] === 'string';

        if (isMulti) {
          // Multiselect mode (string array options like type names)
          def.filter = 'agTextColumnFilter';
          def.floatingFilter = true;
          def.filterParams = {
            filterOptions: ['contains'],
            suppressAndOrCondition: true,
            textMatcher: (params: any) => {
              const model = params.filterModel;
              if (model?.type === 'inSet' && model.values) {
                return model.values.includes(params.value);
              }
              if (model?.filter) {
                return String(params.value ?? '').toLowerCase().includes(String(model.filter).toLowerCase());
              }
              return true;
            },
          };
          def.floatingFilterComponent = MultiSelectFloatingFilter;
          def.floatingFilterComponentParams = {
            suppressFilterButton: true,
            filterOptions: options,
            filterPlaceholder: col.header ? `All ${col.header}s` : 'All',
          };
        } else {
          // Single select mode (boolean status or {label, value} options)
          def.filter = 'agTextColumnFilter';
          def.floatingFilter = true;

          if (isBoolean) {
            // Boolean filter (Active/Inactive)
            def.filterParams = {
              filterOptions: ['equals'],
              suppressAndOrCondition: true,
              textMatcher: (params: any) => {
                const filterVal = params.filterModel?.filter;
                if (filterVal == null) return true;
                const rowVal = String(params.value);
                return rowVal === filterVal;
              },
            };
            def.floatingFilterComponent = SelectFloatingFilter;
            def.floatingFilterComponentParams = {
              suppressFilterButton: true,
              filterOptions: options.map((o: any) => ({
                label: o.label,
                value: String(o.value),
              })),
              filterPlaceholder: 'All',
            };
            // Convert boolean to string for filter matching
            const origValueGetter = def.valueGetter;
            if (!origValueGetter) {
              def.valueGetter = (params) => String(params.data?.[col.field]);
            }
          } else {
            def.filterParams = {
              filterOptions: ['equals'],
              suppressAndOrCondition: true,
            };
            def.floatingFilterComponent = SelectFloatingFilter;
            def.floatingFilterComponentParams = {
              suppressFilterButton: true,
              filterOptions: options,
              filterPlaceholder: 'All',
            };
          }
        }
        break;
      }

      case 'none':
      default:
        def.filter = false;
        def.floatingFilter = false;
        break;
    }
  }

  private resolveFilterOptions(col: DataTableColumn<T>): any[] {
    if (!col.filterOptions) return [];
    if (isSignal(col.filterOptions)) {
      return col.filterOptions() ?? [];
    }
    if (typeof col.filterOptions === 'function') {
      return (col.filterOptions as any)() ?? [];
    }
    return col.filterOptions;
  }

  // ─── Auto-column generation (partition-style) ─────────────
  private buildAutoColumns(): ColDef[] {
    const data = this._rowData() as Record<string, any>[];
    if (data.length === 0) return [];

    const useLinks = this.autoLinks();
    const cols = Object.keys(data[0]).filter(col => !HIDDEN_COLUMNS.has(col));

    return cols.map(col => {
      const isLink = useLinks && isLinkColumn(col, data);
      const isKey = KEY_COLUMNS.has(col) || isLink;
      const def: ColDef = { headerName: formatHeader(col), field: col };

      if (isKey) {
        def.cellStyle = {
          fontFamily: 'monospace',
          whiteSpace: 'nowrap',
          background: 'color-mix(in srgb, var(--fg) 4%, transparent)',
        };
      }

      if (isLink) {
        def.cellRenderer = PartitionLinkCellRenderer;
        def.cellRendererParams = { colField: col, router: this.router };
      }

      if (DATE_COLUMNS.has(col)) {
        def.valueFormatter = (params) => {
          if (!params.value) return '';
          return this.datePipe.transform(params.value, 'yyyy-MM-dd HH:mm:ss ZZZZZ') ?? String(params.value);
        };
      }

      return def;
    });
  }
}
