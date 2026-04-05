import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
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
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Paginator } from 'primeng/paginator';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../../shared/empty-state.component';

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
    DatePicker,
    TableModule,
    SelectButton,
    Button,
    Tag,
    Paginator,
    Card,
    Skeleton,
    EmptyStateComponent,
    UniversePanelComponent,
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

  // Runs tab state
  strategyRuns = signal<StrategyRunListItem[]>([]);
  runsTotal = signal(0);
  runsTotalPages = signal(0);
  runsPage = signal(1);
  runsFilterMode = signal<'none' | 'range' | 'around'>('none');
  runsRangeFrom = signal<Date | null>(null);
  runsRangeTo = signal<Date | null>(null);
  runsAroundDatetime = signal<Date | null>(null);
  runsAroundRadius = signal<5 | 10 | 30 | 60>(5);
  runsRadiusOptions: (5 | 10 | 30 | 60)[] = [5, 10, 30, 60];

  runsFilterOptions = [
    { label: 'All', value: 'none' },
    { label: 'Range', value: 'range' },
    { label: 'Around', value: 'around' },
  ];

  runsRadiusSelectOptions = [
    { label: '5m', value: 5 },
    { label: '10m', value: 10 },
    { label: '30m', value: 30 },
    { label: '1h', value: 60 },
  ];

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
      this.runsFilterMode.set('none');

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
    this.feedService.loadStrategyRuns(this.strategyId, this.runsPage(), 20, this.buildRunsFilter()).subscribe({
      next: (res) => {
        this.strategyRuns.set(res.items);
        this.runsTotal.set(res.total);
        this.runsTotalPages.set(res.total_pages);
      },
    });
  }

  onRunsPageChange(newPage: number): void {
    this.runsPage.set(newPage);
    this.loadStrategyRuns();
  }

  setRunsFilterMode(mode: 'none' | 'range' | 'around'): void {
    this.runsFilterMode.set(mode);
    if (mode === 'none') {
      this.runsRangeFrom.set(null);
      this.runsRangeTo.set(null);
      this.runsAroundDatetime.set(null);
      this.runsPage.set(1);
      this.loadStrategyRuns();
    }
  }

  applyRunsFilter(): void {
    this.runsPage.set(1);
    this.loadStrategyRuns();
  }

  clearRunsFilter(): void {
    this.setRunsFilterMode('none');
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

  private buildRunsFilter(): RunFilter | undefined {
    const mode = this.runsFilterMode();
    if (mode === 'range') {
      const f: RunFilter = {};
      const from = this.runsRangeFrom();
      const to = this.runsRangeTo();
      if (from) f.started_after = from.toISOString();
      if (to) f.started_before = to.toISOString();
      if (f.started_after || f.started_before) return f;
    } else if (mode === 'around') {
      const center = this.runsAroundDatetime();
      if (center) {
        const offsetMs = this.runsAroundRadius() * 60 * 1000;
        return {
          started_after: new Date(center.getTime() - offsetMs).toISOString(),
          started_before: new Date(center.getTime() + offsetMs).toISOString(),
        };
      }
    }
    return undefined;
  }
}
