import { DatePipe, NgTemplateOutlet } from '@angular/common';
import {
  Component,
  EventEmitter,
  Output,
  TemplateRef,
  ViewChild,
  computed,
  effect,
  inject,
  input,
  isSignal,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { MultiSelect } from 'primeng/multiselect';
import { Skeleton } from 'primeng/skeleton';
import { Table, TableLazyLoadEvent, TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { AppEmptyStateComponent } from '../empty-state/app-empty-state.component';
import { generateAutoColumns } from './auto-columns';
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '../../../constants/pagination';
import {
  AppColumn,
  AppColumnState,
  AppFetchFn,
  AppFilterOption,
  AppSeverity,
} from './app-column.model';

const STORAGE_PREFIX = 'ascent-table-';

/**
 * PrimeNG p-table wrapper providing the redesign's standard list-page UX:
 *
 *   - Server-side pagination via [fetchPage] (lazy load).
 *   - Sort, filter (text / select / multiselect / date / number / none).
 *   - Column resize, reorder, pinning (frozen left/right), visibility toggle.
 *   - CSV export from the toolbar.
 *   - Cell renderers: text, monospace, link, tag, status, currency, date,
 *     number, and arbitrary [cellTemplate].
 *   - localStorage persistence of column visibility / order / widths via
 *     [storageKey].
 *
 * Ag-grid is no longer in use; this is the only data-table primitive.
 */
@Component({
  selector: 'app-data-table',
  standalone: true,
  imports: [
    TableModule,
    Button,
    MultiSelect,
    InputText,
    Skeleton,
    Tag,
    NgTemplateOutlet,
    RouterLink,
    FormsModule,
    AppEmptyStateComponent,
  ],
  host: {
    class: 'w-full',
    '[class.flex]': 'fillHeight()',
    '[class.flex-col]': 'fillHeight()',
    '[class.min-h-0]': 'fillHeight()',
    '[class.h-full]': 'fillHeight()',
  },
  styles: [`
    /* Stretch the empty-message row to fill the table body so the
       empty state lives in the full vertical space, not at the top. */
    :host ::ng-deep tr.app-data-table-empty,
    :host ::ng-deep tr.app-data-table-empty > td {
      height: 100%;
    }
    :host ::ng-deep .p-datatable-tbody {
      height: 100%;
    }
    :host ::ng-deep tr.app-data-table-empty > td {
      vertical-align: middle;
      border: none;
    }

    /* Grid-lines mode: explicit borders on every cell, both axes. PrimeNG's
       showGridlines covers most cases but we add the right-edge / bottom-edge
       borders to make sure scrollable tables get full grid coverage. */
    :host ::ng-deep .app-data-table--gridlines .p-datatable-thead > tr > th,
    :host ::ng-deep .app-data-table--gridlines .p-datatable-tbody > tr > td,
    :host ::ng-deep .app-data-table--gridlines .p-datatable-tfoot > tr > td {
      border-right: 1px solid var(--edge);
      border-bottom: 1px solid var(--edge);
    }
    :host ::ng-deep .app-data-table--gridlines .p-datatable-thead > tr > th:last-child,
    :host ::ng-deep .app-data-table--gridlines .p-datatable-tbody > tr > td:last-child,
    :host ::ng-deep .app-data-table--gridlines .p-datatable-tfoot > tr > td:last-child {
      border-right: none;
    }
  `],
  template: `
    @if (showToolbar()) {
      <div class="flex items-center justify-between gap-2 px-2 py-1.5 border-b border-edge shrink-0">
        <div class="flex items-center gap-2">
          @if (enableGlobalFilter()) {
            <span class="relative">
              <i class="pi pi-search absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint text-xs"></i>
              <input
                pInputText
                type="text"
                [placeholder]="globalFilterPlaceholder()"
                class="pl-7 text-xs"
                style="width: 14rem;"
                (input)="onGlobalFilterInput($event)"
              />
            </span>
          }
          <ng-content select="[toolbar-left]" />
        </div>
        <div class="flex items-center gap-2">
          <ng-content select="[toolbar-right]" />
          @if (enableColumnToggle()) {
            <p-multiSelect
              [options]="toggleableColumns()"
              [ngModel]="visibleFieldsModel()"
              (ngModelChange)="visibleFieldsModel.set($event)"
              optionLabel="header"
              optionValue="field"
              placeholder="Columns"
              [showHeader]="false"
              [filter]="false"
              size="small"
              styleClass="text-xs"
              [maxSelectedLabels]="0"
              selectedItemsLabel="{0} columns"
              (onChange)="persistState()"
            />
          }
          @if (enableExport()) {
            <p-button
              icon="pi pi-download"
              severity="secondary"
              [text]="true"
              size="small"
              [rounded]="true"
              pTooltip="Export CSV"
              (onClick)="exportCsv()"
            />
          }
        </div>
      </div>
    }

    <p-table
      #table
      [value]="rowData()"
      [columns]="visibleColumns()"
      [lazy]="!isStaticMode()"
      [loading]="loading()"
      [paginator]="showPaginator() && !isStaticMode() || (isStaticMode() && total() > pageSizeState())"
      [rows]="pageSizeState()"
      [totalRecords]="total()"
      [first]="first()"
      [rowsPerPageOptions]="pageSizeOptions()"
      [showCurrentPageReport]="true"
      currentPageReportTemplate="Showing {first} to {last} of {totalRecords}"
      [scrollable]="fillHeight()"
      [scrollHeight]="fillHeight() ? 'flex' : undefined"
      [resizableColumns]="true"
      columnResizeMode="expand"
      [reorderableColumns]="true"
      [responsiveLayout]="'scroll'"
      [sortMode]="'single'"
      [showGridlines]="gridLines()"
      [exportFilename]="exportFilename()"
      [styleClass]="(fillHeight() ? 'flex-1 min-h-0 ' : '') + (edgeToEdge() ? '' : 'border border-edge rounded-md') + (gridLines() ? ' app-data-table--gridlines' : '')"
      (onLazyLoad)="onLazyLoad($event)"
      (onColResize)="onColResize($event)"
      (onColReorder)="onColReorder($event)"
    >
      <ng-template pTemplate="header" let-cols>
        <tr>
          @for (col of cols; track col.field; let i = $index) {
            <th
              [pSortableColumn]="col.sortable !== false ? col.field : ''"
              [pSortableColumnDisabled]="col.sortable === false"
              pReorderableColumn
              pResizableColumn
              pFrozenColumn
              [frozen]="!!col.pinned"
              [alignFrozen]="col.pinned === 'right' ? 'right' : 'left'"
              [style.width.px]="columnWidth(col)"
              [style.min-width.px]="col.minWidth ?? undefined"
              class="text-[11px] uppercase tracking-wider font-semibold text-fg-muted"
            >
              <div class="flex items-center gap-1">
                <span>{{ col.header }}</span>
                @if (col.sortable !== false) {
                  <p-sortIcon [field]="col.field" />
                }
              </div>
            </th>
          }
        </tr>
        @if (hasFilters()) {
          <tr>
            @for (col of cols; track col.field) {
              <th pFrozenColumn
                  [frozen]="!!col.pinned"
                  [alignFrozen]="col.pinned === 'right' ? 'right' : 'left'">
                @switch (col.filter) {
                  @case ('text') {
                    <input
                      pInputText
                      type="text"
                      class="w-full text-xs"
                      placeholder="Search"
                      (input)="onColumnFilterInput(col.field, $event)"
                    />
                  }
                  @case ('select') {
                    <p-multiSelect
                      [options]="resolveOptions(col)"
                      optionLabel="label"
                      optionValue="value"
                      placeholder="All"
                      [showHeader]="false"
                      [filter]="false"
                      size="small"
                      styleClass="w-full text-xs"
                      [selectionLimit]="1"
                      [maxSelectedLabels]="1"
                      (onChange)="onColumnFilterSelect(col.field, $event.value)"
                    />
                  }
                  @case ('multiselect') {
                    <p-multiSelect
                      [options]="resolveOptions(col)"
                      optionLabel="label"
                      optionValue="value"
                      placeholder="All"
                      [showHeader]="false"
                      [filter]="false"
                      size="small"
                      styleClass="w-full text-xs"
                      (onChange)="onColumnFilterSelect(col.field, $event.value)"
                    />
                  }
                  @default {}
                }
              </th>
            }
          </tr>
        }
      </ng-template>

      <ng-template pTemplate="body" let-row let-cols="columns">
        <tr
          [class.cursor-pointer]="!!rowClickRoute()"
          [class]="rowClassFor(row)"
          (click)="onRowClick(row)"
        >
          @for (col of cols; track col.field) {
            <td
              pFrozenColumn
              [frozen]="!!col.pinned"
              [alignFrozen]="col.pinned === 'right' ? 'right' : 'left'"
              [class]="cellClass(col, row)"
              [style.width.px]="columnWidth(col)"
            >
              <ng-container [ngTemplateOutlet]="cellTpl(col)"
                            [ngTemplateOutletContext]="{ $implicit: row, col: col }" />
            </td>
          }
        </tr>
      </ng-template>

      <ng-template pTemplate="emptymessage">
        <tr class="app-data-table-empty">
          <td [attr.colspan]="visibleColumns().length">
            <div class="flex items-center justify-center w-full" style="min-height: 12rem;">
              <app-empty-state [title]="emptyMessage()" />
            </div>
          </td>
        </tr>
      </ng-template>

      <ng-template pTemplate="loadingbody" let-cols="columns">
        @for (_ of skeletonRows; track $index) {
          <tr>
            @for (col of cols; track col.field) {
              <td><p-skeleton height="0.875rem" /></td>
            }
          </tr>
        }
      </ng-template>
    </p-table>

    <ng-template #defaultCell let-row let-col="col">
      @switch (col.cellType ?? 'text') {
        @case ('monospace') {
          <span class="font-mono text-xs text-fg-muted tabular-nums">{{ formatValue(col, row) }}</span>
        }
        @case ('currency') {
          <span class="font-mono tabular-nums">{{ formatCurrency(col, row) }}</span>
        }
        @case ('number') {
          <span class="tabular-nums">{{ formatValue(col, row) }}</span>
        }
        @case ('date') {
          <span class="text-xs text-fg-muted">{{ formatDate(col, row) }}</span>
        }
        @case ('link') {
          @if (linkTarget(col, row); as target) {
            <a [routerLink]="target" class="text-primary hover:underline" (click)="$event.stopPropagation()">
              {{ formatValue(col, row) }}
            </a>
          } @else {
            <span>{{ formatValue(col, row) }}</span>
          }
        }
        @case ('tag') {
          @if (col.tagMapper) {
            <p-tag [value]="col.tagMapper!(getValue(col, row), row).label"
                   [severity]="col.tagMapper!(getValue(col, row), row).severity" />
          } @else {
            <p-tag [value]="formatValue(col, row)" severity="secondary" />
          }
        }
        @case ('status') {
          @if (col.tagMapper) {
            <p-tag [value]="col.tagMapper!(getValue(col, row), row).label"
                   [severity]="col.tagMapper!(getValue(col, row), row).severity" [rounded]="true" />
          } @else {
            <p-tag [value]="formatValue(col, row)" severity="secondary" [rounded]="true" />
          }
        }
        @default {
          <span>{{ formatValue(col, row) }}</span>
        }
      }
    </ng-template>
  `,
})
export class AppDataTableComponent<T = any> {
  // ─── Column / data inputs ─────────────────────────────────
  columns = input<AppColumn<T>[]>([]);
  /** Server-paginated fetch fn. Provide either this OR `value` (static rows). */
  fetchPage = input<AppFetchFn<T> | null>(null);
  /** Static row data. Use when the parent owns the data set (e.g. embedded
   * tables on a detail page). When provided, paginator is hidden by default. */
  value = input<T[] | null>(null);
  /** When true and no `columns` are provided, columns are auto-generated
   * from the row data keys (or from server-supplied `columns` ordering).
   * Used by partition-style result tables (Data Explorer, run views). */
  autoColumns = input(false);
  /** When auto-generating columns, treat known display columns (provider,
   * instrument, etc.) as router links to their entity detail pages. */
  autoLinks = input(false);

  // ─── Pagination ───────────────────────────────────────────
  pageSize = input(DEFAULT_PAGE_SIZE);
  pageSizeOptions = input<number[]>(PAGE_SIZE_OPTIONS);
  showPaginator = input(true);

  // ─── Toolbar features ─────────────────────────────────────
  showToolbar = input(false);
  enableExport = input(false);
  enableColumnToggle = input(false);
  enableGlobalFilter = input(false);
  globalFilterPlaceholder = input('Search…');
  exportFilename = input<string>('export');

  // ─── Behavior ─────────────────────────────────────────────
  rowClickRoute = input<((row: T) => string | any[] | null) | null>(null);
  rowClass = input<((row: T) => string | null | undefined) | null>(null);
  emptyMessage = input('No data found.');
  edgeToEdge = input(false);
  gridLines = input(false);
  /** When true (default) the host stretches with ``h-full`` and the inner
   *  p-table is scrollable + uses ``scrollHeight="flex"`` so tables fill the
   *  remaining space in a flex column. Set to false for static-mode short
   *  tables that should size to their row count rather than expand to the
   *  available height. */
  fillHeight = input(true);

  // ─── State persistence ────────────────────────────────────
  storageKey = input<string | undefined>(undefined);

  // ─── Outputs ──────────────────────────────────────────────
  sortChange = output<{ field: string; order: 'asc' | 'desc' }>();
  pageChange = output<number>();
  pageSizeChange = output<number>();
  rowClick = output<T>();
  dataLoaded = output<T[]>();

  // ─── Internal state ───────────────────────────────────────
  /** Server-fetched rows (lazy-load mode). Updated by ``onLazyLoad``. In
   *  static mode (``[value]`` provided) this stays empty; ``rowData`` reads
   *  ``value()`` directly so static tables always reflect the current input
   *  without an effect-copy timing gap. */
  private serverRowData = signal<T[]>([]);
  rowData = computed<T[]>(() => {
    const v = this.value();
    return v ?? this.serverRowData();
  });
  total = signal(0);
  first = signal(0);
  pageSizeState = signal(DEFAULT_PAGE_SIZE);
  loading = signal(false);
  filters = signal<Record<string, any>>({});
  globalFilter = signal<string>('');
  sortState = signal<{ field: string; order: 'asc' | 'desc' } | undefined>(undefined);
  serverColumns = signal<string[] | null>(null);

  /** Signal so the ``visibleColumns`` computed re-runs when the visibility
   *  effect populates this post-construction. (Was previously a plain
   *  property — the computed never recomputed and the table rendered with
   *  zero columns until a sort triggered a fresh template evaluation.) */
  visibleFieldsModel = signal<string[]>([]);
  private columnState = signal<AppColumnState | null>(null);

  effectiveColumns = computed<AppColumn<T>[]>(() => {
    const explicit = this.columns();
    if (explicit.length > 0) return explicit;
    if (!this.autoColumns()) return [];
    const sample = this.rowData()[0] as Record<string, any> | undefined;
    return generateAutoColumns<any>(sample, {
      withLinks: this.autoLinks(),
      serverColumns: this.serverColumns(),
    }) as AppColumn<T>[];
  });

  @ViewChild('table') tableRef?: Table;
  /** Signal-based viewChild so the cell template binding re-evaluates the
   *  moment the ref is resolved by the view. Previously a plain ``@ViewChild``
   *  returned ``undefined`` during the first render — every cell rendered
   *  empty until something (a sort, a click) triggered a re-evaluation. */
  defaultCellTpl = viewChild<TemplateRef<{ $implicit: T; col: AppColumn<T> }>>('defaultCell');

  skeletonRows = Array.from({ length: 8 });

  private router = inject(Router);
  private datePipe = new DatePipe('en-US');
  private filterDebounce: any;

  toggleableColumns = computed(() =>
    this.effectiveColumns().map((c) => ({ field: c.field, header: c.header })),
  );

  visibleColumns = computed<AppColumn<T>[]>(() => {
    const all = this.effectiveColumns();
    const state = this.columnState();
    const visibleFields = new Set(this.visibleFieldsModel());
    const ordered = state?.order
      ? state.order.map((f) => all.find((c) => c.field === f)).filter(Boolean) as AppColumn<T>[]
      : all;
    const missing = all.filter((c) => !ordered.includes(c));
    return [...ordered, ...missing].filter((c) => visibleFields.has(c.field));
  });

  hasFilters = computed(() =>
    this.effectiveColumns().some((c) => c.filter && c.filter !== 'none'),
  );

  constructor() {
    effect(() => {
      const cols = this.effectiveColumns();
      const state = this.columnState();
      const explicitVisible = cols
        .filter((c) => c.visible !== false)
        .map((c) => c.field);
      const stored = state?.visible
        ? cols.filter((c) => state.visible[c.field] !== false).map((c) => c.field)
        : explicitVisible;
      untracked(() => {
        this.visibleFieldsModel.set(stored);
      });
    });

    effect(() => {
      const ps = this.pageSize();
      untracked(() => this.pageSizeState.set(ps));
    });

    effect(() => {
      const key = this.storageKey();
      if (!key) return;
      untracked(() => {
        const stored = this.readStoredState(key);
        if (stored) this.columnState.set(stored);
      });
    });

    // Static-data mode: keep ``total`` / ``loading`` in sync with the
    // ``[value]`` input. ``rowData`` itself is a computed that reads
    // ``value()`` directly, so the static table always reflects the input
    // without an effect-copy timing gap.
    effect(() => {
      const v = this.value();
      if (v != null) {
        untracked(() => {
          this.total.set(v.length);
          this.loading.set(false);
        });
      }
    });
  }

  isStaticMode(): boolean {
    return this.value() != null;
  }

  // ─── Lazy load ────────────────────────────────────────────
  onLazyLoad(event: TableLazyLoadEvent): void {
    const fn = this.fetchPage();
    if (!fn) return;

    if (event.first != null) this.first.set(event.first);
    if (event.rows != null && event.rows !== this.pageSizeState()) {
      this.pageSizeState.set(event.rows);
      this.pageSizeChange.emit(event.rows);
    }

    if (event.sortField && typeof event.sortField === 'string') {
      const order: 'asc' | 'desc' = event.sortOrder === -1 ? 'desc' : 'asc';
      const next = { field: event.sortField, order };
      this.sortState.set(next);
      this.sortChange.emit(next);
    } else {
      this.sortState.set(undefined);
    }

    const page = Math.floor(this.first() / this.pageSizeState()) + 1;
    this.pageChange.emit(page);

    this.loading.set(true);
    fn(page, this.pageSizeState(), this.sortState()).subscribe({
      next: (res) => {
        this.serverRowData.set(res.items);
        this.total.set(res.total);
        this.serverColumns.set(res.columns ?? null);
        this.loading.set(false);
        this.dataLoaded.emit(res.items);
      },
      error: () => this.loading.set(false),
    });
  }

  // ─── Row click ────────────────────────────────────────────
  onRowClick(row: T): void {
    this.rowClick.emit(row);
    const route = this.rowClickRoute();
    if (route) {
      const target = route(row);
      if (target == null) return;
      const cmds = Array.isArray(target) ? target : [target];
      this.router.navigate(cmds);
    }
  }

  // ─── Toolbar actions ──────────────────────────────────────
  exportCsv(): void {
    this.tableRef?.exportCSV();
  }

  onGlobalFilterInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.globalFilter.set(value);
    this.debouncedReload();
  }

  onColumnFilterInput(field: string, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.filters.update((f) => ({ ...f, [field]: value || undefined }));
    this.debouncedReload();
  }

  onColumnFilterSelect(field: string, value: any): void {
    const empty = Array.isArray(value) ? value.length === 0 : value == null || value === '';
    this.filters.update((f) => ({ ...f, [field]: empty ? undefined : value }));
    this.debouncedReload();
  }

  private debouncedReload(): void {
    clearTimeout(this.filterDebounce);
    this.filterDebounce = setTimeout(() => {
      this.first.set(0);
      this.tableRef?.clear();
      this.tableRef?._filter();
    }, 250);
  }

  // ─── Column state persistence ─────────────────────────────
  onColResize(event: any): void {
    const field = event.element?.getAttribute('data-pc-section');
    const widths = { ...(this.columnState()?.widths ?? {}) };
    const colField = event.element?.dataset?.field;
    if (colField && event.delta != null) {
      const current = widths[colField] ?? event.element.offsetWidth;
      widths[colField] = Math.max(40, current + event.delta);
    }
    this.updateColumnState({ widths });
  }

  onColReorder(event: any): void {
    const order = event.columns?.map((c: any) => c.field).filter(Boolean) ?? [];
    if (order.length > 0) this.updateColumnState({ order });
  }

  persistState(): void {
    const visible: Record<string, boolean> = {};
    for (const col of this.effectiveColumns()) {
      visible[col.field] = this.visibleFieldsModel().includes(col.field);
    }
    this.updateColumnState({ visible });
  }

  private updateColumnState(patch: Partial<AppColumnState>): void {
    const next: AppColumnState = {
      visible: { ...(this.columnState()?.visible ?? {}), ...(patch.visible ?? {}) },
      order: patch.order ?? this.columnState()?.order ?? [],
      widths: { ...(this.columnState()?.widths ?? {}), ...(patch.widths ?? {}) },
    };
    this.columnState.set(next);
    const key = this.storageKey();
    if (!key) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }

  private readStoredState(key: string): AppColumnState | null {
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      return {
        visible: parsed.visible ?? {},
        order: Array.isArray(parsed.order) ? parsed.order : [],
        widths: parsed.widths ?? {},
      };
    } catch {
      return null;
    }
  }

  // ─── Cell helpers ─────────────────────────────────────────
  cellTpl(col: AppColumn<T>): any {
    return col.cellTemplate ?? this.defaultCellTpl();
  }

  cellClass(col: AppColumn<T>, row: T): string {
    const cls = col.cellClass;
    if (typeof cls === 'function') return cls(row);
    return cls ?? '';
  }

  rowClassFor(row: T): string {
    const fn = this.rowClass();
    return fn?.(row) ?? '';
  }

  columnWidth(col: AppColumn<T>): number | undefined {
    const stored = this.columnState()?.widths?.[col.field];
    return stored ?? col.width;
  }

  getValue(col: AppColumn<T>, row: T): any {
    return (row as any)?.[col.field];
  }

  formatValue(col: AppColumn<T>, row: T): string {
    const value = this.getValue(col, row);
    if (col.format) return col.format(value, row);
    if (value == null) return '';
    return String(value);
  }

  formatCurrency(col: AppColumn<T>, row: T): string {
    const value = this.getValue(col, row);
    if (value == null || value === '') return '';
    if (col.format) return col.format(value, row);
    const num = typeof value === 'number' ? value : Number(value);
    if (Number.isNaN(num)) return String(value);
    return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  formatDate(col: AppColumn<T>, row: T): string {
    const value = this.getValue(col, row);
    if (!value) return '';
    if (col.format) return col.format(value, row);
    return this.datePipe.transform(value, 'MMM d, yyyy HH:mm:ss') ?? String(value);
  }

  linkTarget(col: AppColumn<T>, row: T): string | any[] | null {
    return col.linkRoute ? col.linkRoute(row) : null;
  }

  resolveOptions(col: AppColumn<T>): AppFilterOption[] {
    const opts = col.filterOptions;
    if (!opts) return [];
    if (Array.isArray(opts)) return opts;
    if (isSignal(opts)) return (opts as any)();
    return [];
  }
}
