import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { map } from 'rxjs/operators';
import { StrategyService } from '../../../services/strategy.service';
import { FeedService } from '../../../services/feed.service';
import { TradeService } from '../../../services/trade.service';
import { ToastService } from '../../../services/toast.service';
import { ApiService } from '../../../services/api.service';
import { StrategyFeedDAG } from '../../../models/feed.model';
import { OrderListItem } from '../../../models/order.model';
import { TradeListItem, PaginatedResponse } from '../../../models/trade.model';
import { StrategyExchangeItem } from '../../../models/exchange.model';
import { ExchangeService } from '../../../services/exchange.service';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { StrategyRunsTabComponent } from './strategy-runs-tab.component';
import { CumulativePnlChartComponent, CumulativePnlPoint, Lookback, LOOKBACK_OPTIONS } from './charts/cumulative-pnl-chart.component';
import { PnlDistributionChartComponent } from './charts/pnl-distribution-chart.component';
import { Button } from 'primeng/button';
import { SelectButton } from 'primeng/selectbutton';
import { FormsModule } from '@angular/forms';

import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';

import { ServerTableComponent } from '../../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../../shared/data-table/data-table.model';
import { StageCellRenderer, StatusBadgeCellRenderer, RemoveCellRenderer } from '../../shared/universe-panel.component';
import { UniverseImpactDialogComponent, ImpactDialogChoice } from '../../shared/universe-impact-dialog.component';
import { ImpactReport } from '../../../models/asset.model';
import type { ColDef } from 'ag-grid-community';

const CURRENCY_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
});

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    FormsModule,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    TradeTableComponent,
    CumulativePnlChartComponent,
    PnlDistributionChartComponent,
    Button,
    SelectButton,
    Tag,
    Card,
    Skeleton,
    UniversePanelComponent,
    UniverseImpactDialogComponent,
    ServerTableComponent,
    StrategyRunsTabComponent,
  ],
  templateUrl: './strategy-detail.component.html',
})
export class StrategyDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  private api = inject(ApiService);
  strategyService = inject(StrategyService);
  feedService = inject(FeedService);
  tradeService = inject(TradeService);

  exchangeService = inject(ExchangeService);

  tabs = ['Overview', 'Trades', 'Orders', 'Universe', 'Exchanges', 'Runs', 'Configuration'];
  activeTab = signal('Overview');
  editing = signal(false);
  editedParameters = signal<Record<string, any>>({});
  feedDag = signal<StrategyFeedDAG | null>(null);

  // Order columns
  orderColumns: DataTableColumn[] = [
    { field: 'instrument_name', header: 'Pair', sortable: false },
    { field: 'side', header: 'Side', cellType: 'tag', tagMapper: (v: string) => ({ label: v, severity: v === 'BUY' ? 'success' : v === 'SELL' ? 'danger' : 'secondary' }) },
    { field: 'order_type', header: 'Type', sortable: false, cellClass: 'text-muted-color' },
    { field: 'quantity', header: 'Qty' },
    { field: 'price', header: 'Price', valueFormatter: (p: any) => this.formatCurrency(p.value) },
    { field: 'filled_quantity', header: 'Filled', valueGetter: (p: any) => p.data?.filled_quantity !== null ? `${p.data.filled_quantity} / ${p.data.quantity}` : '\u2014' },
    { field: 'current_status', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: string) => {
      if (!v) return { label: '', severity: 'secondary' };
      const map: Record<string, string> = { FILLED: 'success', PARTIALLY_FILLED: 'warn', SUBMITTED: 'warn', ACCEPTED: 'warn', REJECTED: 'danger', CANCELLED: 'secondary' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
  ];


  // Server-side fetch functions for child table components
  ordersFetchPage = computed<ServerFetchFn<OrderListItem> | null>(() => {
    this.strategyService.selectedStrategy(); // track strategy changes
    const id = this.strategyId;
    if (!id) return null;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<OrderListItem>>(`/strategies/${id}/orders`, params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  tradesFetchPage = computed<ServerFetchFn<TradeListItem> | null>(() => {
    this.strategyService.selectedStrategy(); // track strategy changes
    const id = this.strategyId;
    if (!id) return null;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<TradeListItem>>(`/strategies/${id}/trades`, params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  // Exchange columns for the current exchanges view (with remove button)
  exchangeColumns: DataTableColumn[] = [
    { field: 'exchange_display_name', header: 'Exchange', sortable: false },
    { field: 'exchange_name', header: 'Name', sortable: false, cellClass: 'font-mono text-surface-500' },
    { field: 'provider_name', header: 'Provider', sortable: false },
    { field: 'is_active', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: boolean) => ({ label: v ? 'Active' : 'Inactive', severity: v ? 'success' : 'secondary' }) },
    { field: '', header: '', sortable: false, cellType: 'custom', cellRenderer: RemoveCellRenderer, width: 80 },
  ];

  exchangeGridContext = {
    onRemove: (id: string) => this.removeExchange(id),
  };

  exchangesFetchPage = computed<ServerFetchFn<StrategyExchangeItem> | null>(() => {
    this.strategyService.selectedStrategy(); // track strategy changes
    const id = this.strategyId;
    if (!id) return null;
    return (page: number, pageSize: number) => {
      return this.api.get<PaginatedResponse<StrategyExchangeItem>>(`/strategies/${id}/exchanges/search`, { page, page_size: pageSize }).pipe(
        map(res => {
          this.exchangeCount.set(res.total);
          return { items: res.items, total: res.total };
        })
      );
    };
  });

  // Picker columns using ag-grid ColDef with StageCellRenderer
  exchangePickerColDefs: ColDef[] = [
    { headerName: 'Display Name', field: 'display_name', minWidth: 160 },
    { headerName: 'Name', field: 'name', cellClass: 'font-mono text-surface-500', minWidth: 140 },
    { headerName: 'Provider', field: 'provider_name', sortable: false },
    { headerName: 'Status', field: 'is_active', cellRenderer: StatusBadgeCellRenderer },
    { headerName: '', field: '', cellRenderer: StageCellRenderer, sortable: false, maxWidth: 80 },
  ];

  exchangePickerContext = {
    isStaged: (id: string) => this.stagedExchangeIds().has(id),
    toggleStage: (id: string) => this.toggleStageExchange(id),
  };

  getExchangeRowStyle = (params: any) => {
    const id = params.data?.id;
    if (id && this.stagedExchangeIds().has(id)) {
      return {
        background: 'rgba(34, 197, 94, 0.08)',
        borderLeft: '3px solid rgb(34, 197, 94)',
      };
    }
    return undefined;
  };

  exchangePickerFetchPage = computed<ServerFetchFn<any> | null>(() => {
    const id = this.strategyId;
    if (!id) return null;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      return this.exchangeService.loadExchangesPaginated(page, pageSize, { is_active: true }, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  // Stats from API
  stats = computed(() => this.strategyService.strategyStats());

  // Chart data from stats
  cumulativePnlData = computed<CumulativePnlPoint[]>(() => this.stats()?.cumulative_pnl ?? []);
  pnlLookback = signal<Lookback>('all');
  lookbackOptions = LOOKBACK_OPTIONS;
  pnlDistributionData = computed<number[]>(() => {
    const bins = this.stats()?.pnl_distribution ?? [];
    // Expand histogram bins back into individual values for the chart component
    const values: number[] = [];
    for (const bin of bins) {
      for (let i = 0; i < bin.count; i++) {
        values.push(bin.center);
      }
    }
    return values;
  });

  formatDuration(seconds: number | null): string {
    if (seconds === null) return 'N/A';
    const totalMinutes = Math.abs(seconds) / 60;
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = Math.floor(totalMinutes % 60);
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  }

  strategyId = '';
  strategyHasExchanges = computed(() => this.exchangeCount() > 0);

  constructor() {}

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.strategyId) return;
      this.strategyId = id;

      // Restore tab and run from query params (for back-navigation)
      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Overview');
      }
      // Reset state for the new strategy
      this.editing.set(false);
      this.editedParameters.set({});
      this.feedDag.set(null);

      this.strategyService.loadStrategyDetail(this.strategyId);
      this.strategyService.loadStrategyStats(this.strategyId);
      this.feedService.loadStrategyFeedDAG(this.strategyId).subscribe({
        next: (dag) => this.feedDag.set(dag),
      });
      // Eagerly check exchange count so strategyHasExchanges is set before user visits Universe tab
      this.api.get<PaginatedResponse<StrategyExchangeItem>>(`/strategies/${id}/exchanges/search`, { page: 1, page_size: 1 }).subscribe({
        next: (res) => this.exchangeCount.set(res.total),
      });
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.updateQueryParams({ tab });
  }

  private updateQueryParams(params: Record<string, string | null>): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: params,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  skeletonRows(count: number): number[] {
    return Array.from({ length: count }, (_, i) => i);
  }

  startEditing(): void {
    const strategy = this.strategyService.selectedStrategy();
    if (strategy?.parameters) {
      this.editedParameters.set({ ...strategy.parameters as Record<string, any> });
    }
    this.editing.set(true);
  }

  cancelEditing(): void {
    this.editing.set(false);
    this.editedParameters.set({});
  }

  onParametersChange(values: Record<string, any>): void {
    this.editedParameters.set(values);
  }

  saveParameters(): void {
    const strategy = this.strategyService.selectedStrategy();
    if (!strategy) return;

    this.strategyService.saving.set(true);
    this.strategyService.updateStrategy(strategy.id, { parameters: this.editedParameters() }).subscribe({
      next: () => {
        this.strategyService.saving.set(false);
        this.editing.set(false);
        this.strategyService.loadStrategyDetail(strategy.id, true);
        this.toast.success('Parameters saved successfully.');
      },
      error: () => {
        this.strategyService.saving.set(false);
        this.toast.error('Failed to save parameters.');
      },
    });
  }

  formatCurrency(value: number): string {
    return CURRENCY_FORMATTER.format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-positive' : 'text-negative';
  }

  orderSideSeverity(side: string): 'success' | 'danger' | 'secondary' {
    switch (side.toUpperCase()) {
      case 'BUY': return 'success';
      case 'SELL': return 'danger';
      default: return 'secondary';
    }
  }

  orderStatusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' {
    switch (status.toUpperCase()) {
      case 'FILLED':
      case 'COMPLETED': return 'success';
      case 'REJECTED':
      case 'CANCELLED':
      case 'FAILED': return 'danger';
      case 'PARTIALLY_FILLED':
      case 'SUBMITTED':
      case 'ACCEPTED': return 'warn';
      default: return 'secondary';
    }
  }

  // --- Universe tab methods ---

  onAddInstruments(event: { instrumentIds: string[]; startOrder: number }): void {
    this.strategyService.batchAddInstruments(this.strategyId, event.instrumentIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.instrumentIds.length} instrument(s) added to universe`);
      },
      error: () => this.toast.error('Failed to add instruments to universe'),
    });
  }

  removeUniverseItem(instrumentId: string): void {
    this.openImpactDialog({
      kind: 'instrument',
      id: instrumentId,
      label: 'Instrument',
      load: this.strategyService.getUniverseItemImpact(this.strategyId, instrumentId),
      remove: () => this.strategyService.removeUniverseItem(this.strategyId, instrumentId),
      disable: () => this.strategyService.setUniverseItemActive(this.strategyId, instrumentId, false),
    });
  }

  onAddComposites(event: { compositeIds: string[]; startOrder: number }): void {
    this.strategyService.batchAddComposites(this.strategyId, event.compositeIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.compositeIds.length} composite(s) added to universe`);
      },
      error: () => this.toast.error('Failed to add composites to universe'),
    });
  }

  removeCompositeItem(compositeId: string): void {
    this.openImpactDialog({
      kind: 'composite',
      id: compositeId,
      label: 'Composite',
      load: this.strategyService.getCompositeUniverseItemImpact(this.strategyId, compositeId),
      remove: () => this.strategyService.removeCompositeUniverseItem(this.strategyId, compositeId),
      disable: () => this.strategyService.setCompositeUniverseItemActive(this.strategyId, compositeId, false),
    });
  }

  onToggleInstrumentActive(event: { id: string; isActive: boolean }): void {
    this.strategyService.setUniverseItemActive(this.strategyId, event.id, event.isActive).subscribe({
      next: () => this.toast.success(event.isActive ? 'Instrument enabled' : 'Instrument disabled'),
      error: (err) => this.toast.error(err?.error?.message ?? 'Failed to update instrument'),
    });
  }

  onToggleCompositeActive(event: { id: string; isActive: boolean }): void {
    this.strategyService.setCompositeUniverseItemActive(this.strategyId, event.id, event.isActive).subscribe({
      next: () => this.toast.success(event.isActive ? 'Composite enabled' : 'Composite disabled'),
      error: (err) => this.toast.error(err?.error?.message ?? 'Failed to update composite'),
    });
  }

  // --- Exchanges tab methods ---

  showExchangePicker = signal(false);
  stagedExchangeIds = signal<Set<string>>(new Set());
  exchangeCount = signal(0);

  openExchangePicker(): void {
    this.stagedExchangeIds.set(new Set());
    this.showExchangePicker.set(true);
  }

  cancelExchangePicker(): void {
    this.showExchangePicker.set(false);
    this.stagedExchangeIds.set(new Set());
  }

  toggleStageExchange(id: string): void {
    this.stagedExchangeIds.update(s => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  submitStagedExchanges(): void {
    const ids = Array.from(this.stagedExchangeIds());
    if (ids.length === 0) return;
    this.strategyService.batchAddExchanges(this.strategyId, ids, this.exchangeCount() + 1).subscribe({
      next: () => {
        this.toast.success(`${ids.length} exchange(s) added`);
        this.showExchangePicker.set(false);
        this.stagedExchangeIds.set(new Set());
      },
      error: () => this.toast.error('Failed to add exchanges'),
    });
  }

  removeExchange(exchangeId: string): void {
    this.openImpactDialog({
      kind: 'exchange',
      id: exchangeId,
      label: 'Exchange',
      load: this.strategyService.getExchangeImpact(this.strategyId, exchangeId),
      remove: () => this.strategyService.removeExchange(this.strategyId, exchangeId),
      disable: () => this.strategyService.setExchangeActive(this.strategyId, exchangeId, false),
    });
  }

  // --- Impact dialog plumbing ---

  impactDialogVisible = signal(false);
  impactReport = signal<ImpactReport | null>(null);
  impactBusy = signal(false);
  impactEntityLabel = signal('Item');
  impactEntityName = signal<string | null>(null);
  impactSupportsDisable = signal(true);

  private impactCurrent: {
    remove: () => import('rxjs').Observable<any>;
    disable: () => import('rxjs').Observable<any>;
    successMessage: string;
    disableMessage: string;
  } | null = null;

  private openImpactDialog(opts: {
    kind: 'instrument' | 'composite' | 'exchange';
    id: string;
    label: string;
    load: import('rxjs').Observable<ImpactReport>;
    remove: () => import('rxjs').Observable<any>;
    disable: () => import('rxjs').Observable<any>;
  }): void {
    this.impactCurrent = {
      remove: opts.remove,
      disable: opts.disable,
      successMessage: `${opts.label} removed`,
      disableMessage: `${opts.label} disabled`,
    };
    this.impactEntityLabel.set(opts.label);
    this.impactEntityName.set(null);
    this.impactReport.set(null);
    this.impactBusy.set(false);
    this.impactSupportsDisable.set(true);
    this.impactDialogVisible.set(true);

    opts.load.subscribe({
      next: (report) => this.impactReport.set(report),
      error: () => {
        this.toast.error('Failed to compute impact');
        this.impactDialogVisible.set(false);
      },
    });
  }

  onImpactDecision(choice: ImpactDialogChoice): void {
    if (choice === 'cancel') {
      this.impactDialogVisible.set(false);
      this.impactCurrent = null;
      return;
    }
    const op = this.impactCurrent;
    if (!op) return;
    this.impactBusy.set(true);
    const stream = choice === 'remove' ? op.remove() : op.disable();
    stream.subscribe({
      next: () => {
        this.toast.success(choice === 'remove' ? op.successMessage : op.disableMessage);
        this.impactBusy.set(false);
        this.impactDialogVisible.set(false);
        this.impactCurrent = null;
        // Reload strategy detail so signals like is_paused or table contents refresh.
        this.strategyService.loadStrategyDetail(this.strategyId, true);
      },
      error: (err) => {
        this.impactBusy.set(false);
        const msg = err?.error?.message ?? `Failed to ${choice} item`;
        this.toast.error(msg);
      },
    });
  }

  // --- Pause / resume ---

  pauseBusy = signal(false);

  togglePause(currentlyPaused: boolean): void {
    this.pauseBusy.set(true);
    this.strategyService.pauseStrategy(this.strategyId, !currentlyPaused).subscribe({
      next: () => {
        this.pauseBusy.set(false);
        this.toast.success(currentlyPaused ? 'Strategy resumed' : 'Strategy paused');
        this.strategyService.loadStrategyDetail(this.strategyId, true);
      },
      error: () => {
        this.pauseBusy.set(false);
        this.toast.error('Failed to update pause state');
      },
    });
  }

}
