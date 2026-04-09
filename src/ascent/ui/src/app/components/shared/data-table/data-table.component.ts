import {
  Component,
  computed,
  inject,
  input,
  output,
  isSignal,
} from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AgGridAngular } from 'ag-grid-angular';
import type {
  ColDef,
  GridApi,
  GridReadyEvent,
  RowClickedEvent,
} from 'ag-grid-community';
import { ThemeService } from '../../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './ag-grid-theme';
import type { DataTableColumn } from './data-table.model';
import {
  StatusCellRenderer,
  TagCellRenderer,
  LinkCellRenderer,
  CurrencyCellRenderer,
} from './cell-renderers';
import { SelectFloatingFilter, MultiSelectFloatingFilter } from './floating-filters';

@Component({
  selector: 'app-data-table',
  standalone: true,
  imports: [AgGridAngular],
  template: `
    <div [attr.data-ag-theme-mode]="themeMode()" class="rounded-lg overflow-clip border border-edge">
      <ag-grid-angular
        [theme]="theme"
        [rowData]="rowData()"
        [columnDefs]="agColumnDefs()"
        [defaultColDef]="defaultColDef()"
        [domLayout]="'autoHeight'"
        [pagination]="pagination()"
        [paginationPageSize]="pageSize()"
        [paginationPageSizeSelector]="pageSizeOptions()"
        [loading]="loading()"
        [suppressCellFocus]="true"
        [overlayNoRowsTemplate]="noRowsHtml()"
        [rowClass]="rowClickRoute() ? 'cursor-pointer' : ''"
        (gridReady)="onGridReady($event)"
        (rowClicked)="onRowClicked($event)"/>
    </div>
  `,
  styles: [`
    :host { display: block; }
    :host ::ng-deep .ag-row.cursor-pointer { cursor: pointer; }
    :host ::ng-deep .ag-header-cell:last-child .ag-header-cell-resize { display: none; }
  `],
})
export class DataTableComponent<T = any> {
  // Core inputs
  columns = input.required<DataTableColumn<T>[]>();
  rowData = input<T[]>([]);
  loading = input(false);

  // Pagination
  pagination = input(true);
  pageSize = input(25);
  pageSizeOptions = input<number[] | false>([25, 50, 100]);

  // Behavior
  rowClickRoute = input<((row: T) => string | any[]) | null>(null);
  emptyMessage = input('No data found.');

  // Outputs
  rowClick = output<T>();

  // Internal
  private router = inject(Router);
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;
  private gridApi: GridApi | null = null;

  private datePipe = new DatePipe('en-US');
  private decimalPipe = new DecimalPipe('en-US');

  noRowsHtml = computed(() =>
    `<span style="font-size: 12px; opacity: 0.5;">${this.emptyMessage()}</span>`
  );

  defaultColDef = computed<ColDef>(() => {
    const hasFilters = this.columns().some(c => c.filterType && c.filterType !== 'none');
    return {
      sortable: true,
      resizable: false,
      suppressMovable: true,
      floatingFilter: hasFilters,
      filter: false,
      flex: 1,
    };
  });

  agColumnDefs = computed<ColDef[]>(() => {
    return this.columns().map(col => this.toColDef(col));
  });

  onGridReady(event: GridReadyEvent): void {
    this.gridApi = event.api;
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
        if (col.tagMapper) def.cellRendererParams = { tagMapper: col.tagMapper };
        break;
      case 'tag':
        def.cellRenderer = TagCellRenderer;
        if (col.tagMapper) def.cellRendererParams = { tagMapper: col.tagMapper };
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
        if (col.valueFormatter) def.valueFormatter = col.valueFormatter;
        break;
      case 'custom':
        if (col.cellRenderer) def.cellRenderer = col.cellRenderer;
        if (col.cellRendererParams) def.cellRendererParams = col.cellRendererParams;
        break;
    }

    if (col.valueFormatter && col.cellType !== 'number') def.valueFormatter = col.valueFormatter;
    if (col.valueGetter) def.valueGetter = col.valueGetter;
    if (col.cellClass) def.cellClass = col.cellClass;

    this.applyFilter(def, col);
    return def;
  }

  private applyFilter(def: ColDef, col: DataTableColumn<T>): void {
    switch (col.filterType) {
      case 'text':
        def.filter = 'agTextColumnFilter';
        def.floatingFilter = true;
        def.filterParams = { filterOptions: ['contains'], suppressAndOrCondition: true, debounceMs: 200 };
        def.floatingFilterComponentParams = { suppressFilterButton: true };
        break;

      case 'select': {
        const options = this.resolveFilterOptions(col);
        const isBoolean = options.length > 0 && typeof options[0]?.value === 'boolean';
        const isMulti = !isBoolean && options.length > 0 && typeof options[0] === 'string';

        if (isMulti) {
          def.filter = 'agTextColumnFilter';
          def.floatingFilter = true;
          def.filterParams = {
            filterOptions: ['contains'],
            suppressAndOrCondition: true,
            textMatcher: (params: any) => {
              const model = params.filterModel;
              if (model?.type === 'inSet' && model.values) return model.values.includes(params.value);
              if (model?.filter) return String(params.value ?? '').toLowerCase().includes(String(model.filter).toLowerCase());
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
          def.filter = 'agTextColumnFilter';
          def.floatingFilter = true;
          if (isBoolean) {
            def.filterParams = {
              filterOptions: ['equals'],
              suppressAndOrCondition: true,
              textMatcher: (params: any) => {
                const filterVal = params.filterModel?.filter;
                if (filterVal == null) return true;
                return String(params.value) === filterVal;
              },
            };
            def.floatingFilterComponent = SelectFloatingFilter;
            def.floatingFilterComponentParams = {
              suppressFilterButton: true,
              filterOptions: options.map((o: any) => ({ label: o.label, value: String(o.value) })),
              filterPlaceholder: 'All',
            };
            if (!def.valueGetter) def.valueGetter = (params) => String(params.data?.[col.field]);
          } else {
            def.filterParams = { filterOptions: ['equals'], suppressAndOrCondition: true };
            def.floatingFilterComponent = SelectFloatingFilter;
            def.floatingFilterComponentParams = { suppressFilterButton: true, filterOptions: options, filterPlaceholder: 'All' };
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
    if (isSignal(col.filterOptions)) return col.filterOptions() ?? [];
    if (typeof col.filterOptions === 'function') return (col.filterOptions as any)() ?? [];
    return col.filterOptions;
  }
}
