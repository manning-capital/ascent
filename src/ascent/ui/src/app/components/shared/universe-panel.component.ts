import { Component, computed, EventEmitter, inject, input, OnInit, Output, signal, TemplateRef, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { AssetService } from '../../services/asset.service';
import { CompositeService } from '../../services/composite.service';
import { ApiService } from '../../services/api.service';
import { Instrument, UniverseItem } from '../../models/asset.model';
import { Composite, CompositeUniverseItem } from '../../models/composite.model';
import { PaginatedResponse } from '../../models/trade.model';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';

const ACTIVE_TAG = (v: boolean) => ({
  label: v ? 'Active' : 'Disabled',
  severity: (v ? 'success' : 'secondary') as AppSeverity,
});

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
    AppDataTableComponent,
  ],
  host: { style: 'display:flex;flex-direction:column;flex:1;min-height:0' },
  template: `
    <ng-template #toggleActiveTpl let-row>
      @if (row.is_active) {
        <button (click)="onToggleActive($event, row, false)"
                class="text-xs text-warning hover:underline">Disable</button>
      } @else {
        <button (click)="onToggleActive($event, row, true)"
                class="text-xs text-positive hover:underline">Enable</button>
      }
    </ng-template>

    <ng-template #removeTpl let-row>
      <button (click)="onRemove($event, row)"
              class="text-xs text-negative hover:underline">Remove</button>
    </ng-template>

    <ng-template #stageTpl let-row>
      @if (stagedIds().has(row.id)) {
        <button (click)="onToggleStage($event, row.id)"
                class="text-xs text-positive hover:underline">Staged</button>
      } @else {
        <button (click)="onToggleStage($event, row.id)"
                class="text-xs text-primary hover:underline">Add</button>
      }
    </ng-template>

    <div class="flex flex-col flex-1 min-h-0 p-6">
      @if (!showForm()) {
        <!-- Universe view -->
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div class="flex items-center gap-4">
            <div>
              <h3 class="font-semibold text-sm">Universe</h3>
              <p class="text-xs text-fg-faint mt-1">{{ subtitle() }}</p>
            </div>
            @if (!restrictMode()) {
              <p-selectButton
                [options]="modeOptions"
                [ngModel]="mode()"
                (ngModelChange)="onModeChange($event)"
                optionLabel="label"
                optionValue="value"
                size="small"/>
            }
          </div>
          @if (hasExchanges()) {
            <p-button
              [label]="mode() === 'instruments' ? '+ Add Instruments' : '+ Add Composites'"
              [outlined]="true"
              size="small"
              (onClick)="openForm()"/>
          }
        </div>

        @if (!hasExchanges()) {
          <div class="flex items-center justify-center flex-1 min-h-0">
            <div class="text-center p-8">
              <p class="text-sm text-fg-muted mb-1">No exchanges configured</p>
              <p class="text-xs text-fg-faint">Add exchanges to this strategy before adding instruments or composites to the universe.</p>
            </div>
          </div>
        } @else if (mode() === 'instruments') {
          <app-data-table class="flex-1 min-h-0"
            [columns]="instrumentUniverseColumns()"
            [fetchPage]="instrumentUniverseFetchFn()"
            [rowClass]="universeRowClass"
            emptyMessage="No instruments in universe."/>
        } @else {
          <app-data-table class="flex-1 min-h-0"
            [columns]="compositeUniverseColumns()"
            [fetchPage]="compositeUniverseFetchFn()"
            [rowClass]="universeRowClass"
            emptyMessage="No composites in universe."/>
        }
      } @else {
        <!-- Add items view -->
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div>
            <h3 class="font-semibold text-sm">{{ mode() === 'instruments' ? 'Select Instruments' : 'Select Composites' }}</h3>
            <p class="text-xs text-fg-faint mt-1">{{ stagedIds().size }} staged</p>
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

        <!-- Available items table -->
        <app-data-table class="flex-1 min-h-0"
          [columns]="mode() === 'instruments' ? instrumentPickerColumns() : compositePickerColumns()"
          [fetchPage]="pickerFetchFn()"
          [rowClass]="pickerRowClass"
          [emptyMessage]="mode() === 'instruments' ? 'No instruments found.' : 'No composites found.'"/>
      }
    </div>
  `,
})
export class UniversePanelComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  assetService = inject(AssetService);
  compositeService = inject(CompositeService);

  private toggleActiveTpl = viewChild<TemplateRef<{ $implicit: any }>>('toggleActiveTpl');
  private removeTpl = viewChild<TemplateRef<{ $implicit: any }>>('removeTpl');
  private stageTpl = viewChild<TemplateRef<{ $implicit: any }>>('stageTpl');

  ngOnInit(): void {
    this.assetService.loadInstrumentTypes();
    this.compositeService.loadCompositeTypes();
    const locked = this.restrictMode();
    if (locked) {
      this.mode.set(locked);
    } else {
      const savedMode = this.route.snapshot.queryParamMap.get('universeMode');
      if (savedMode === 'instruments' || savedMode === 'composites') {
        this.mode.set(savedMode);
      }
    }
  }

  onModeChange(newMode: 'instruments' | 'composites'): void {
    this.mode.set(newMode);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { universeMode: newMode },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  refresh(): void {
    this.refreshTrigger.update(v => v + 1);
  }

  // ─── Inputs ───────────────────────────────────────────────
  subtitle = input('Items in this universe.');
  excludeStrategyId = input<string | null>(null);
  excludeFeedId = input<string | null>(null);
  /** Base URL for fetching the instrument universe, e.g. '/strategies/{id}' */
  universeBaseUrl = input<string | null>(null);
  /** When set, restrict picker results to instruments/composites tradeable on this strategy's exchanges. */
  restrictToStrategyId = input<string | null>(null);
  /** When set, restrict picker results to instruments/composites matching the feed's provider + type constraints. */
  restrictToFeedId = input<string | null>(null);
  /** When set, locks the mode toggle to 'instruments' or 'composites'. */
  restrictMode = input<'instruments' | 'composites' | null>(null);
  /** Whether the parent entity has exchanges configured. When false, shows a message instead of the picker. */
  hasExchanges = input(true);

  // ─── Outputs ──────────────────────────────────────────────
  @Output() addInstruments = new EventEmitter<{ instrumentIds: string[]; startOrder: number }>();
  @Output() addComposites = new EventEmitter<{ compositeIds: string[]; startOrder: number }>();
  @Output() removeInstrument = new EventEmitter<string>();
  @Output() removeComposite = new EventEmitter<string>();
  @Output() toggleInstrumentActive = new EventEmitter<{ id: string; isActive: boolean }>();
  @Output() toggleCompositeActive = new EventEmitter<{ id: string; isActive: boolean }>();

  // ─── State ────────────────────────────────────────────────
  mode = signal<'instruments' | 'composites'>('instruments');
  modeOptions = [
    { label: 'Instruments', value: 'instruments' },
    { label: 'Composites', value: 'composites' },
  ];

  showForm = signal(false);
  stagedIds = signal<Set<string>>(new Set());
  stagingAll = signal(false);
  private refreshTrigger = signal(0);

  // Track universe sizes for startOrder calculation
  private instrumentCount = signal(0);
  private compositeCount = signal(0);

  // Filters
  searchFilter = signal('');
  typeFilter = signal<string>('');
  statusFilter = signal<boolean | ''>(true);

  statusFilterOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  // ─── Cell template handlers ───────────────────────────────
  onToggleActive(e: Event, row: any, isActive: boolean): void {
    e.stopPropagation();
    const id = row?.instrument_id ?? row?.composite_id ?? row?.exchange_id ?? row?.id;
    if (this.mode() === 'instruments') {
      this.toggleInstrumentActive.emit({ id, isActive });
    } else {
      this.toggleCompositeActive.emit({ id, isActive });
    }
  }

  onRemove(e: Event, row: any): void {
    e.stopPropagation();
    const id = row?.instrument_id ?? row?.composite_id ?? row?.exchange_id ?? row?.id;
    if (this.mode() === 'instruments') {
      this.removeInstrument.emit(id);
    } else {
      this.removeComposite.emit(id);
    }
  }

  onToggleStage(e: Event, id: string): void {
    e.stopPropagation();
    this.stagedIds.update(s => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  // ─── Universe view columns ────────────────────────────────
  instrumentUniverseColumns = computed<AppColumn<UniverseItem>[]>(() => {
    const toggleTpl = this.toggleActiveTpl();
    const removeTpl = this.removeTpl();
    if (!toggleTpl || !removeTpl) return [];
    return [
      { field: 'instrument_display_name', header: 'Instrument', sortable: false },
      { field: 'instrument_name', header: 'Name', sortable: false, cellClass: 'font-mono text-fg-muted' },
      { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ACTIVE_TAG(v) },
      { field: '__toggle', header: '', sortable: false, cellTemplate: toggleTpl, width: 90 },
      { field: '__remove', header: '', sortable: false, cellTemplate: removeTpl, width: 80 },
    ];
  });

  compositeUniverseColumns = computed<AppColumn<CompositeUniverseItem>[]>(() => {
    const toggleTpl = this.toggleActiveTpl();
    const removeTpl = this.removeTpl();
    if (!toggleTpl || !removeTpl) return [];
    return [
      { field: 'composite_display_name', header: 'Composite', sortable: false },
      { field: 'composite_name', header: 'Name', sortable: false, cellClass: 'font-mono text-fg-muted' },
      { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ACTIVE_TAG(v) },
      { field: '__toggle', header: '', sortable: false, cellTemplate: toggleTpl, width: 90 },
      { field: '__remove', header: '', sortable: false, cellTemplate: removeTpl, width: 80 },
    ];
  });

  // ─── Picker columns ───────────────────────────────────────
  instrumentPickerColumns = computed<AppColumn<any>[]>(() => {
    const stageTpl = this.stageTpl();
    if (!stageTpl) return [];
    return [
      { field: 'display_name', header: 'Display Name', minWidth: 160 },
      { field: 'name', header: 'Name', cellClass: 'font-mono text-fg-muted', minWidth: 140 },
      { field: 'instrument_type_id', header: 'Type', sortable: false, format: (v) => this.getInstrumentTypeName(v) },
      {
        field: 'pair', header: 'Pair', sortable: false, cellClass: 'font-mono text-fg-muted',
        format: (_, row) => `${row?.from_asset_name ?? ''}/${row?.to_asset_name ?? ''}`,
      },
      { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ACTIVE_TAG(v) },
      { field: '__stage', header: '', sortable: false, cellTemplate: stageTpl, width: 80 },
    ];
  });

  compositePickerColumns = computed<AppColumn<any>[]>(() => {
    const stageTpl = this.stageTpl();
    if (!stageTpl) return [];
    return [
      { field: 'display_name', header: 'Display Name', minWidth: 160 },
      { field: 'name', header: 'Name', cellClass: 'font-mono text-fg-muted', minWidth: 140 },
      { field: 'composite_type_id', header: 'Type', sortable: false, format: (v) => this.getCompositeTypeName(v) },
      { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ACTIVE_TAG(v) },
      { field: '__stage', header: '', sortable: false, cellTemplate: stageTpl, width: 80 },
    ];
  });

  // ─── Row classes ──────────────────────────────────────────
  universeRowClass = (row: any) => row?.is_active === false ? 'opacity-55' : '';

  pickerRowClass = (row: any) => {
    const id = row?.id;
    return id && this.stagedIds().has(id) ? 'app-picker-row-staged' : '';
  };

  // ─── Universe fetch functions ─────────────────────────────
  instrumentUniverseFetchFn = computed<AppFetchFn<UniverseItem> | null>(() => {
    const baseUrl = this.universeBaseUrl();
    if (!baseUrl) return null;
    this.mode();
    this.refreshTrigger();
    return (page, pageSize) =>
      this.api.get<PaginatedResponse<UniverseItem>>(`${baseUrl}/universe/search`, { page, page_size: pageSize }).pipe(
        map(res => {
          this.instrumentCount.set(res.total);
          return { items: res.items, total: res.total };
        }),
      );
  });

  compositeUniverseFetchFn = computed<AppFetchFn<CompositeUniverseItem> | null>(() => {
    const baseUrl = this.universeBaseUrl();
    if (!baseUrl) return null;
    this.mode();
    this.refreshTrigger();
    return (page, pageSize) =>
      this.api.get<PaginatedResponse<CompositeUniverseItem>>(`${baseUrl}/composite-universe/search`, { page, page_size: pageSize }).pipe(
        map(res => {
          this.compositeCount.set(res.total);
          return { items: res.items, total: res.total };
        }),
      );
  });

  // ─── Picker fetch functions ───────────────────────────────
  pickerFetchFn = computed<AppFetchFn<any> | null>(() => {
    const currentMode = this.mode();
    const search = this.searchFilter();
    const typeId = this.typeFilter();
    const status = this.statusFilter();
    const excludeStrategyId = this.excludeStrategyId();
    const excludeFeedId = this.excludeFeedId();
    const restrictToStrategyId = this.restrictToStrategyId();
    const restrictToFeedId = this.restrictToFeedId();

    const params: Record<string, any> = {};
    if (search) params['search'] = search;
    if (status !== '') params['is_active'] = status;
    if (excludeStrategyId) params['exclude_strategy_id'] = excludeStrategyId;
    if (excludeFeedId) params['exclude_feed_id'] = excludeFeedId;
    if (restrictToStrategyId) params['restrict_to_strategy_id'] = restrictToStrategyId;
    if (restrictToFeedId) params['restrict_to_feed_id'] = restrictToFeedId;

    if (currentMode === 'instruments') {
      if (typeId) params['instrument_type_id'] = typeId;
      return (page, pageSize, sort) => {
        const p: Record<string, any> = { ...params, page, page_size: pageSize };
        if (sort) { p['sort_field'] = sort.field; p['sort_order'] = sort.order; }
        return this.api.get<PaginatedResponse<Instrument>>('/instruments/search', p).pipe(
          map(res => ({ items: res.items, total: res.total }))
        );
      };
    } else {
      if (typeId) params['composite_type_id'] = typeId;
      return (page, pageSize, sort) => {
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
  }

  stageAllFiltered(): void {
    const params: Record<string, any> = {};
    const search = this.searchFilter();
    const typeId = this.typeFilter();
    const status = this.statusFilter();
    const excludeStrategyId = this.excludeStrategyId();
    const excludeFeedId = this.excludeFeedId();
    const restrictToStrategyId = this.restrictToStrategyId();
    const restrictToFeedId = this.restrictToFeedId();
    if (search) params['search'] = search;
    if (status !== '') params['is_active'] = status;
    if (excludeStrategyId) params['exclude_strategy_id'] = excludeStrategyId;
    if (excludeFeedId) params['exclude_feed_id'] = excludeFeedId;
    if (restrictToStrategyId) params['restrict_to_strategy_id'] = restrictToStrategyId;
    if (restrictToFeedId) params['restrict_to_feed_id'] = restrictToFeedId;

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
