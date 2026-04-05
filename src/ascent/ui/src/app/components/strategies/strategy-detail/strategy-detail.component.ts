import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { StrategyService } from '../../../services/strategy.service';
import { FeedService } from '../../../services/feed.service';
import { TradeService } from '../../../services/trade.service';
import { ToastService } from '../../../services/toast.service';
import { StrategyFeedDAG, StrategyRunListItem } from '../../../models/feed.model';
import { UniverseItem } from '../../../models/asset.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { RunFilter } from '../../shared/run-viewer.component';
import { CumulativePnlChartComponent, CumulativePnlPoint } from './charts/cumulative-pnl-chart.component';
import { PnlDistributionChartComponent } from './charts/pnl-distribution-chart.component';
import { Button } from 'primeng/button';
import { RunFilterPanelComponent } from '../../shared/run-filter-panel.component';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../../shared/empty-state.component';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import type { DataTableColumn } from '../../shared/data-table/data-table.model';

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    TradeTableComponent,
    CumulativePnlChartComponent,
    PnlDistributionChartComponent,
    Button,
    RunFilterPanelComponent,
    Tag,
    Card,
    Skeleton,
    EmptyStateComponent,
    UniversePanelComponent,
    DataTableComponent,
  ],
  templateUrl: './strategy-detail.component.html',
})
export class StrategyDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  strategyService = inject(StrategyService);
  feedService = inject(FeedService);
  tradeService = inject(TradeService);

  tabs = ['Overview', 'Trades', 'Universe', 'Runs', 'Configuration'];
  activeTab = signal('Overview');
  page = signal(1);
  tradesPageSize = signal(10);
  ordersPage = signal(1);
  ordersPageSize = signal(10);
  editing = signal(false);
  editedParameters = signal<Record<string, any>>({});
  feedDag = signal<StrategyFeedDAG | null>(null);

  // Order columns
  orderColumns: DataTableColumn[] = [
    { field: 'instrument_name', header: 'Pair' },
    { field: 'side', header: 'Side', cellType: 'tag', tagMapper: (v: string) => ({ label: v, severity: v === 'BUY' ? 'success' : v === 'SELL' ? 'danger' : 'secondary' }) },
    { field: 'order_type', header: 'Type', cellClass: 'text-muted-color' },
    { field: 'quantity', header: 'Qty' },
    { field: 'price', header: 'Price', valueFormatter: (p: any) => this.formatCurrency(p.value) },
    { field: 'filled_quantity', header: 'Filled', valueGetter: (p: any) => p.data?.filled_quantity !== null ? `${p.data.filled_quantity} / ${p.data.quantity}` : '\u2014' },
    { field: 'current_status', header: 'Status', cellType: 'tag', tagMapper: (v: string) => {
      if (!v) return { label: '', severity: 'secondary' };
      const map: Record<string, string> = { FILLED: 'success', PARTIALLY_FILLED: 'warn', SUBMITTED: 'warn', ACCEPTED: 'warn', REJECTED: 'danger', CANCELLED: 'secondary' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
  ];

  // Run columns
  runColumns: DataTableColumn<StrategyRunListItem>[] = [
    { field: 'status', header: 'Status', cellType: 'tag', width: 96, tagMapper: (v: string) => {
      const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
    { field: 'id', header: 'Run ID', cellType: 'monospace' },
    { field: 'started_at', header: 'Started', cellType: 'date' },
    { field: 'duration', header: 'Duration', valueGetter: (p: any) => this.runDurationLabel(p.data) },
    { field: 'feed_runs', header: 'Feeds', valueGetter: (p: any) => p.data?.feed_runs?.length ?? 0 },
    { field: 'error_message', header: 'Error', valueFormatter: (p: any) => p.value ?? '-', cellClass: (p: any) => p.value ? 'text-red-500' : '' },
  ];

  navigateToRun = (row: StrategyRunListItem) => ['/strategies', this.strategyId, 'runs', row.id];

  // Runs tab state
  strategyRuns = signal<StrategyRunListItem[]>([]);
  runsTotal = signal(0);
  runsTotalPages = signal(0);
  runsPage = signal(1);
  runsFilter = signal<RunFilter>({});

  // Stats from API
  stats = computed(() => this.strategyService.strategyStats());

  // Chart data from stats
  cumulativePnlData = computed<CumulativePnlPoint[]>(() => this.stats()?.cumulative_pnl ?? []);
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

  // Universe tab state
  universeItems = signal<UniverseItem[]>([]);

  strategyId = '';

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
      this.page.set(1);
      this.ordersPage.set(1);
      this.editing.set(false);
      this.editedParameters.set({});
      this.feedDag.set(null);
      this.strategyRuns.set([]);
      this.runsTotal.set(0);
      this.runsTotalPages.set(0);
      this.runsPage.set(1);
      this.runsFilter.set({});

      this.strategyService.loadStrategyDetail(this.strategyId);
      this.strategyService.loadStrategyTrades(this.strategyId);
      this.strategyService.loadStrategyStats(this.strategyId);
      this.strategyService.loadStrategyOrders(this.strategyId);
      this.feedService.loadStrategyFeedDAG(this.strategyId).subscribe({
        next: (dag) => this.feedDag.set(dag),
      });
      this.loadStrategyRuns();
      this.loadUniverse();
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

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.strategyService.loadStrategyTrades(this.strategyId, newPage, this.tradesPageSize());
  }

  onOrdersPageChange(newPage: number): void {
    this.ordersPage.set(newPage);
    this.strategyService.loadStrategyOrders(this.strategyId, newPage, this.ordersPageSize());
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
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
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

  // --- Runs tab methods ---

  loadStrategyRuns(): void {
    const filter = this.runsFilter();
    const f = Object.keys(filter).length > 0 ? filter : undefined;
    this.feedService.loadStrategyRuns(this.strategyId, this.runsPage(), 20, f).subscribe({
      next: (res) => {
        this.strategyRuns.set(res.items);
        this.runsTotal.set(res.total);
        this.runsTotalPages.set(res.total_pages);
      },
    });
  }

  onRunsFilterChange(filter: RunFilter): void {
    this.runsFilter.set(filter);
    this.runsPage.set(1);
    this.loadStrategyRuns();
  }

  onRunsPageChange(newPage: number): void {
    this.runsPage.set(newPage);
    this.loadStrategyRuns();
  }

  runStatusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'secondary';
    }
  }

  runDurationLabel(run: StrategyRunListItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  // --- Universe tab methods ---

  loadUniverse(): void {
    this.strategyService.loadUniverse(this.strategyId).subscribe({
      next: items => this.universeItems.set(items),
    });
  }

  onAddInstruments(event: { instrumentIds: string[]; startOrder: number }): void {
    this.strategyService.batchAddInstruments(this.strategyId, event.instrumentIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.instrumentIds.length} instrument(s) added to universe`);
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to add instruments to universe'),
    });
  }

  removeUniverseItem(instrumentId: string): void {
    this.strategyService.removeUniverseItem(this.strategyId, instrumentId).subscribe({
      next: () => {
        this.toast.success('Instrument removed from universe');
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to remove instrument'),
    });
  }

}
