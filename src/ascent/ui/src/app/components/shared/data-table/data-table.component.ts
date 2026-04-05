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
import { FormsModule } from '@angular/forms';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp, IFloatingFilterAngularComp } from 'ag-grid-angular';
import type {
  ColDef,
  GridReadyEvent,
  RowClickedEvent,
  IFloatingFilterParams,
  FilterChangedEvent,
} from 'ag-grid-community';
import { Select } from 'primeng/select';
import { MultiSelect } from 'primeng/multiselect';
import { ThemeService } from '../../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './ag-grid-theme';
import type { DataTableColumn } from './data-table.model';
import {
  StatusCellRenderer,
  TagCellRenderer,
  LinkCellRenderer,
  CurrencyCellRenderer,
} from './cell-renderers';

// ─── Custom floating filter: PrimeNG Select (single) ────────
@Component({
  selector: 'ag-select-floating-filter',
  standalone: true,
  imports: [FormsModule, Select],
  template: `
    <p-select
      [ngModel]="value"
      (ngModelChange)="onChanged($event)"
      [options]="options"
      [placeholder]="placeholder"
      optionLabel="label"
      optionValue="value"
      [showClear]="true"
      [style]="{ width: '100%' }"
      styleClass="ag-floating-select"
      [appendTo]="'body'"
      size="small"/>
  `,
  styles: [`
    :host { display: flex; align-items: center; width: 100%; height: 100%; }
    :host ::ng-deep .ag-floating-select { width: 100%; }
    :host ::ng-deep .ag-floating-select .p-select {
      border: none; border-radius: 0; background: transparent; box-shadow: none;
      min-height: unset; height: 100%; font-size: 0.8rem;
    }
    :host ::ng-deep .ag-floating-select .p-select-label { font-size: 0.8rem; padding: 0 0.5rem; }
  `],
})
export class SelectFloatingFilter implements IFloatingFilterAngularComp {
  value: any = null;
  options: { label: string; value: any }[] = [];
  placeholder = 'All';
  private params!: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string };

  agInit(params: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string }): void {
    this.params = params;
    this.options = params.filterOptions ?? [];
    this.placeholder = params.filterPlaceholder ?? 'All';
  }

  onParentModelChanged(parentModel: any): void {
    this.value = parentModel?.filter ?? null;
  }

  onChanged(value: any): void {
    this.params.parentFilterInstance((instance: any) => {
      if (value == null) {
        instance.setModel(null);
      } else {
        instance.setModel({ filterType: 'text', type: 'equals', filter: value });
      }
    });
  }
}

// ─── Custom floating filter: PrimeNG MultiSelect ────────────
@Component({
  selector: 'ag-multiselect-floating-filter',
  standalone: true,
  imports: [FormsModule, MultiSelect],
  template: `
    <p-multiselect
      [ngModel]="value"
      (ngModelChange)="onChanged($event)"
      [options]="options"
      [placeholder]="placeholder"
      [maxSelectedLabels]="1"
      [selectedItemsLabel]="'{0} selected'"
      [showClear]="true"
      [style]="{ width: '100%' }"
      styleClass="ag-floating-multiselect"
      [appendTo]="'body'"
      size="small"/>
  `,
  styles: [`
    :host { display: flex; align-items: center; width: 100%; height: 100%; }
    :host ::ng-deep .ag-floating-multiselect { width: 100%; }
    :host ::ng-deep .ag-floating-multiselect .p-multiselect {
      border: none; border-radius: 0; background: transparent; box-shadow: none;
      min-height: unset; height: 100%; font-size: 0.8rem;
    }
    :host ::ng-deep .ag-floating-multiselect .p-multiselect-label { font-size: 0.8rem; padding: 0 0.5rem; }
  `],
})
export class MultiSelectFloatingFilter implements IFloatingFilterAngularComp {
  value: any[] = [];
  options: string[] = [];
  placeholder = 'All';
  private params!: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string };

  agInit(params: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string }): void {
    this.params = params;
    this.options = params.filterOptions ?? [];
    this.placeholder = params.filterPlaceholder ?? 'All';
  }

  onParentModelChanged(parentModel: any): void {
    if (!parentModel) {
      this.value = [];
    } else {
      this.value = parentModel.values ?? [];
    }
  }

  onChanged(values: any[]): void {
    this.params.parentFilterInstance((instance: any) => {
      if (!values || values.length === 0) {
        instance.setModel(null);
      } else {
        // Use a custom filter model that the parent text filter interprets
        instance.setModel({ filterType: 'text', type: 'inSet', values });
      }
    });
  }
}

// ─── Custom in-set text filter for multiselect ──────────────
// AG Grid Community doesn't have agSetColumnFilter, so we use
// agTextColumnFilter with a custom doesFilterPass for "in set" matching.

// ─── Main DataTable Component ─────���─────────────────────────
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
  rowData = input.required<T[]>();
  loading = input(false);

  // Pagination
  pagination = input(true);
  pageSize = input(10);
  pageSizeOptions = input<number[] | false>([10, 25, 50, 100]);

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

  onGridReady(_event: GridReadyEvent): void {}

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
}
