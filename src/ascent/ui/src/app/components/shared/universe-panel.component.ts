import { Component, computed, EventEmitter, inject, input, OnInit, Output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { AssetService } from '../../services/asset.service';
import { CompositeService } from '../../services/composite.service';
import { ApiService } from '../../services/api.service';
import { Instrument, UniverseItem } from '../../models/asset.model';
import { Composite, CompositeUniverseItem } from '../../models/composite.model';
import { PaginatedResponse } from '../../models/trade.model';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { badgeStyles } from './data-table/cell-renderers';
import { ServerTableComponent } from './data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from './data-table/data-table.model';

// ─── Stage/Unstage button cell renderer ─────────────────────
@Component({
  selector: 'ag-stage-cell',
  standalone: true,
  template: `
    @if (staged) {
      <button (click)="onClick($event)" class="text-xs text-green-500 hover:underline">Staged</button>
    } @else {
      <button (click)="onClick($event)" class="text-xs text-primary hover:underline">Add</button>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class StageCellRenderer implements ICellRendererAngularComp {
  staged = false;
  private params!: any;

  agInit(params: ICellRendererParams): void { this.params = params; this.staged = params.context?.isStaged(params.data?.id ?? params.data?.instrument_id ?? params.data?.composite_id); }
  refresh(params: ICellRendererParams): boolean { this.params = params; this.staged = params.context?.isStaged(params.data?.id ?? params.data?.instrument_id ?? params.data?.composite_id); return true; }

  onClick(e: Event): void {
    e.stopPropagation();
    const id = this.params.data?.id ?? this.params.data?.instrument_id ?? this.params.data?.composite_id;
    this.params.context?.toggleStage(id);
    this.params.api?.redrawRows();
  }
}

// ─── Status badge cell renderer ─────────────────────────────
@Component({
  selector: 'ag-status-badge',
  standalone: true,
  template: `<span [style]="styles">{{ label }}</span>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class StatusBadgeCellRenderer implements ICellRendererAngularComp {
  label = ''; styles = '';
  agInit(p: ICellRendererParams): void { this.label = p.value ? 'Active' : 'Inactive'; this.styles = badgeStyles(p.value ? 'success' : 'secondary'); }
  refresh(p: ICellRendererParams): boolean { this.agInit(p); return true; }
}

// ─── Remove button cell renderer ────────────────────────────
@Component({
  selector: 'ag-remove-cell',
  standalone: true,
  template: `<button (click)="onClick($event)" class="text-xs text-red-500 hover:underline">Remove</button>`,
  host: { style: 'display:flex;align-items:center;justify-content:flex-end;height:100%;width:100%' },
})
export class RemoveCellRenderer implements ICellRendererAngularComp {
  private params!: any;
  agInit(params: ICellRendererParams): void { this.params = params; }
  refresh(params: ICellRendererParams): boolean { this.params = params; return true; }
  onClick(e: Event): void {
    e.stopPropagation();
    const id = this.params.data?.instrument_id ?? this.params.data?.composite_id;
    this.params.context?.onRemove(id);
  }
}

@Component({
  selector: 'app-universe-panel',
  standalone: true,
  imports: [
    FormsModule,
    InputText,
    Select,
    SelectButton,
    Button,
    Card,
    ServerTableComponent,
  ],
  host: { style: 'display:flex;flex-direction:column;flex:1;min-height:0' },
  template: `
    <div class="flex flex-col flex-1 min-h-0 p-6">
      @if (!showForm()) {
        <!-- Universe view -->
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div class="flex items-center gap-4">
            <div>
              <h3 class="font-semibold text-sm">Universe</h3>
              <p class="text-xs text-surface-400 mt-1">{{ subtitle() }}</p>
            </div>
            <p-selectButton
              [options]="modeOptions"
              [ngModel]="mode()"
              (ngModelChange)="mode.set($event)"
              optionLabel="label"
              optionValue="value"
              size="small"/>
          </div>
          <p-button
            [label]="mode() === 'instruments' ? '+ Add Instruments' : '+ Add Composites'"
            [outlined]="true"
            size="small"
            (onClick)="openForm()"/>
        </div>

        <!-- Current universe server table -->
        @if (mode() === 'instruments') {
          <app-server-table class="flex-1 min-h-0"
            [columns]="instrumentUniverseColumns"
            [fetchPage]="instrumentUniverseFetchFn()"
            [pageSize]="25"
            [gridContext]="universeContext"
            emptyMessage="No instruments in universe."/>
        } @else {
          <app-server-table class="flex-1 min-h-0"
            [columns]="compositeUniverseColumns"
            [fetchPage]="compositeUniverseFetchFn()"
            [pageSize]="25"
            [gridContext]="universeContext"
            emptyMessage="No composites in universe."/>
        }
      } @else {
        <!-- Add items view -->
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div>
            <h3 class="font-semibold text-sm">{{ mode() === 'instruments' ? 'Select Instruments' : 'Select Composites' }}</h3>
            <p class="text-xs text-surface-400 mt-1">{{ stagedIds().size }} staged</p>
          </div>
          <div class="flex items-center gap-2">
            <p-button label="Cancel" severity="secondary" [text]="true" size="small" (onClick)="cancelForm()"/>
            <p-button
              [label]="'Add ' + stagedIds().size + (mode() === 'instruments' ? ' Instrument' : ' Composite') + (stagedIds().size === 1 ? '' : 's')"
              size="small"
              (onClick)="submitStaged()"
              [disabled]="stagedIds().size === 0"/>
          </div>
        </div>

        <!-- Filters -->
        <p-card styleClass="mb-4 shrink-0">
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-2 flex-1">
              <input type="text" pInputText
                [placeholder]="mode() === 'instruments' ? 'Search instruments...' : 'Search composites...'"
                [ngModel]="searchFilter()"
                (ngModelChange)="searchFilter.set($event)"/>
              <p-select
                [ngModel]="typeFilter()"
                (ngModelChange)="typeFilter.set($event)"
                [options]="activeTypeFilterOptions()"
                optionLabel="label"
                optionValue="value"
                [placeholder]="mode() === 'instruments' ? 'All Types' : 'All Types'"
                [showClear]="true"
                appendTo="body"/>
              <p-select
                [ngModel]="statusFilter()"
                (ngModelChange)="statusFilter.set($event)"
                [options]="statusFilterOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="All Statuses"
                [showClear]="true"
                appendTo="body"/>
            </div>
            <div class="flex items-center gap-2">
              @if (stagedIds().size > 0) {
                <p-button label="Unstage All" severity="danger" [outlined]="true" size="small" (onClick)="unstageAll()"/>
              }
              <p-button
                label="Stage All Filtered"
                severity="secondary"
                [outlined]="true"
                size="small"
                [loading]="stagingAll()"
                (onClick)="stageAllFiltered()"/>
            </div>
          </div>
        </p-card>

        <!-- Available items server table -->
        <app-server-table class="flex-1 min-h-0"
          [columnDefs]="mode() === 'instruments' ? instrumentPickerColDefs : compositePickerColDefs"
          [fetchPage]="pickerFetchFn()"
          [pageSize]="25"
          [gridContext]="pickerContext"
          [getRowStyle]="getRowStyle"
          [emptyMessage]="mode() === 'instruments' ? 'No instruments found.' : 'No composites found.'"/>
      }
    </div>
  `,
})
export class UniversePanelComponent implements OnInit {
  private api = inject(ApiService);
  assetService = inject(AssetService);
  compositeService = inject(CompositeService);
  private serverTable = viewChild(ServerTableComponent);

  ngOnInit(): void {
    this.assetService.loadInstrumentTypes();
    this.compositeService.loadCompositeTypes();
  }

  // ─── Inputs ───────────────────────────────────────────────
  subtitle = input('Items in this universe.');
  excludeStrategyId = input<string | null>(null);
  excludeFeedId = input<string | null>(null);
  /** Base URL for fetching the instrument universe, e.g. '/strategies/{id}' */
  universeBaseUrl = input<string | null>(null);

  // ─── Outputs ──────────────────────────────────────────────
  @Output() addInstruments = new EventEmitter<{ instrumentIds: string[]; startOrder: number }>();
  @Output() addComposites = new EventEmitter<{ compositeIds: string[]; startOrder: number }>();
  @Output() removeInstrument = new EventEmitter<string>();
  @Output() removeComposite = new EventEmitter<string>();

  // ─── State ────────────────────────────────────────────────
  mode = signal<'instruments' | 'composites'>('instruments');
  modeOptions = [
    { label: 'Instruments', value: 'instruments' },
    { label: 'Composites', value: 'composites' },
  ];

  showForm = signal(false);
  stagedIds = signal<Set<string>>(new Set());
  stagingAll = signal(false);

  // Track universe sizes for startOrder calculation
  private instrumentCount = signal(0);
  private compositeCount = signal(0);

  // Filters
  searchFilter = signal('');
  typeFilter = signal<string>('');
  statusFilter = signal<boolean | ''>('');

  statusFilterOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  // ─── Universe view columns ────────────────────────────────
  instrumentUniverseColumns: DataTableColumn[] = [
    { field: 'instrument_display_name', header: 'Instrument', sortable: false },
    { field: 'instrument_name', header: 'Name', sortable: false, cellClass: 'font-mono text-surface-500' },
    { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ({ label: v ? 'Active' : 'Inactive', severity: v ? 'success' : 'secondary' }) },
    { field: '', header: '', sortable: false, cellType: 'custom', cellRenderer: RemoveCellRenderer, width: 80 },
  ];

  compositeUniverseColumns: DataTableColumn[] = [
    { field: 'composite_display_name', header: 'Composite', sortable: false },
    { field: 'composite_name', header: 'Name', sortable: false, cellClass: 'font-mono text-surface-500' },
    { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ({ label: v ? 'Active' : 'Inactive', severity: v ? 'success' : 'secondary' }) },
    { field: '', header: '', sortable: false, cellType: 'custom', cellRenderer: RemoveCellRenderer, width: 80 },
  ];

  // ─── Picker columns ──────────────────────────────────────
  instrumentPickerColDefs: ColDef[] = [
    { headerName: 'Display Name', field: 'display_name', minWidth: 160 },
    { headerName: 'Name', field: 'name', cellClass: 'font-mono text-surface-500', minWidth: 140 },
    { headerName: 'Type', field: 'instrument_type_id', sortable: false, valueFormatter: (p) => this.getInstrumentTypeName(p.value) },
    { headerName: 'Pair', field: 'pair', cellClass: 'font-mono text-surface-500', sortable: false, valueGetter: (p) => `${p.data?.from_asset_name ?? ''}/${p.data?.to_asset_name ?? ''}` },
    { headerName: 'Status', field: 'is_active', cellRenderer: StatusBadgeCellRenderer },
    { headerName: '', field: '', cellRenderer: StageCellRenderer, sortable: false, maxWidth: 80 },
  ];

  compositePickerColDefs: ColDef[] = [
    { headerName: 'Display Name', field: 'display_name', minWidth: 160 },
    { headerName: 'Name', field: 'name', cellClass: 'font-mono text-surface-500', minWidth: 140 },
    { headerName: 'Type', field: 'composite_type_id', sortable: false, valueFormatter: (p) => this.getCompositeTypeName(p.value) },
    { headerName: 'Status', field: 'is_active', cellRenderer: StatusBadgeCellRenderer },
    { headerName: '', field: '', cellRenderer: StageCellRenderer, sortable: false, maxWidth: 80 },
  ];

  // ─── Grid contexts ────────────────────────────────────────
  universeContext = {
    onRemove: (id: string) => {
      if (this.mode() === 'instruments') {
        this.removeInstrument.emit(id);
      } else {
        this.removeComposite.emit(id);
      }
    },
  };

  pickerContext = {
    isStaged: (id: string) => this.stagedIds().has(id),
    toggleStage: (id: string) => {
      this.stagedIds.update(s => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id); else n.add(id);
        return n;
      });
    },
  };

  getRowStyle = (params: any) => {
    const id = params.data?.id;
    if (id && this.stagedIds().has(id)) {
      return {
        background: 'rgba(34, 197, 94, 0.08)',
        borderLeft: '3px solid rgb(34, 197, 94)',
      };
    }
    return undefined;
  };

  // ─── Universe fetch functions ─────────────────────────────
  instrumentUniverseFetchFn = computed<ServerFetchFn<UniverseItem> | null>(() => {
    const baseUrl = this.universeBaseUrl();
    if (!baseUrl) return null;
    this.mode(); // track mode changes to force re-evaluation
    return (page: number, pageSize: number) => {
      return this.api.get<PaginatedResponse<UniverseItem>>(`${baseUrl}/universe/search`, { page, page_size: pageSize }).pipe(
        map(res => {
          this.instrumentCount.set(res.total);
          return { items: res.items, total: res.total };
        })
      );
    };
  });

  compositeUniverseFetchFn = computed<ServerFetchFn<CompositeUniverseItem> | null>(() => {
    const baseUrl = this.universeBaseUrl();
    if (!baseUrl) return null;
    this.mode(); // track mode changes
    return (page: number, pageSize: number) => {
      return this.api.get<PaginatedResponse<CompositeUniverseItem>>(`${baseUrl}/composite-universe/search`, { page, page_size: pageSize }).pipe(
        map(res => {
          this.compositeCount.set(res.total);
          return { items: res.items, total: res.total };
        })
      );
    };
  });

  // ─── Picker fetch functions ───────────────────────────────
  pickerFetchFn = computed<ServerFetchFn<any> | null>(() => {
    const currentMode = this.mode();
    const search = this.searchFilter();
    const typeId = this.typeFilter();
    const status = this.statusFilter();
    const excludeStrategyId = this.excludeStrategyId();
    const excludeFeedId = this.excludeFeedId();

    const params: Record<string, any> = {};
    if (search) params['search'] = search;
    if (status !== '') params['is_active'] = status;
    if (excludeStrategyId) params['exclude_strategy_id'] = excludeStrategyId;
    if (excludeFeedId) params['exclude_feed_id'] = excludeFeedId;

    if (currentMode === 'instruments') {
      if (typeId) params['instrument_type_id'] = typeId;
      return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
        const p: Record<string, any> = { ...params, page, page_size: pageSize };
        if (sort) { p['sort_field'] = sort.field; p['sort_order'] = sort.order; }
        return this.api.get<PaginatedResponse<Instrument>>('/instruments/search', p).pipe(
          map(res => ({ items: res.items, total: res.total }))
        );
      };
    } else {
      if (typeId) params['composite_type_id'] = typeId;
      return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
        const p: Record<string, any> = { ...params, page, page_size: pageSize };
        if (sort) { p['sort_field'] = sort.field; p['sort_order'] = sort.order; }
        return this.api.get<PaginatedResponse<Composite>>('/composites/search', p).pipe(
          map(res => ({ items: res.items, total: res.total }))
        );
      };
    }
  });

  // ─── Type filter options ──────────────────────────────────
  instrumentTypeOptions = computed(() =>
    this.assetService.instrumentTypes().map(t => ({ label: t.display_name || t.name, value: t.id }))
  );

  compositeTypeOptions = computed(() =>
    this.compositeService.compositeTypes().map(t => ({ label: t.display_name || t.name, value: t.id }))
  );

  activeTypeFilterOptions = computed(() =>
    this.mode() === 'instruments' ? this.instrumentTypeOptions() : this.compositeTypeOptions()
  );

  getInstrumentTypeName(typeId: string): string {
    return this.assetService.instrumentTypes().find(t => t.id === typeId)?.display_name ?? '';
  }

  getCompositeTypeName(typeId: string): string {
    return this.compositeService.compositeTypes().find(t => t.id === typeId)?.display_name ?? '';
  }

  // ─── Actions ──────────────────────────────────────────────
  openForm(): void {
    this.stagedIds.set(new Set());
    this.searchFilter.set('');
    this.typeFilter.set('');
    this.statusFilter.set('');
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }

  unstageAll(): void {
    this.stagedIds.set(new Set());
    this.serverTable()?.gridApi?.redrawRows();
  }

  stageAllFiltered(): void {
    const params: Record<string, any> = {};
    const search = this.searchFilter();
    const typeId = this.typeFilter();
    const status = this.statusFilter();
    const excludeStrategyId = this.excludeStrategyId();
    const excludeFeedId = this.excludeFeedId();
    if (search) params['search'] = search;
    if (status !== '') params['is_active'] = status;
    if (excludeStrategyId) params['exclude_strategy_id'] = excludeStrategyId;
    if (excludeFeedId) params['exclude_feed_id'] = excludeFeedId;

    const endpoint = this.mode() === 'instruments' ? '/instruments/ids' : '/composites/ids';
    if (this.mode() === 'instruments' && typeId) params['instrument_type_id'] = typeId;
    if (this.mode() === 'composites' && typeId) params['composite_type_id'] = typeId;

    this.stagingAll.set(true);
    this.api.get<string[]>(endpoint, params).subscribe({
      next: (ids) => {
        this.stagedIds.update(s => {
          const n = new Set(s);
          for (const id of ids) n.add(id);
          return n;
        });
        this.stagingAll.set(false);
        this.serverTable()?.gridApi?.redrawRows();
      },
      error: () => this.stagingAll.set(false),
    });
  }

  submitStaged(): void {
    const ids = Array.from(this.stagedIds());
    if (ids.length === 0) return;
    if (this.mode() === 'instruments') {
      this.addInstruments.emit({ instrumentIds: ids, startOrder: this.instrumentCount() + 1 });
    } else {
      this.addComposites.emit({ compositeIds: ids, startOrder: this.compositeCount() + 1 });
    }
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }
}
