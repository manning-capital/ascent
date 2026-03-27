import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { StrategyService } from '../../../services/strategy.service';
import { FeedService } from '../../../services/feed.service';
import { TradeService } from '../../../services/trade.service';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { ToastService } from '../../../services/toast.service';
import { StrategyFeedDAG, StrategyRunListItem } from '../../../models/feed.model';
import { UniverseItem, UniverseItemCreate, AssetGroup } from '../../../models/asset.model';
import { LoadingSpinnerComponent } from '../../shared/loading-spinner.component';
import { PanelTabsComponent } from '../../shared/panel-tabs.component';
import { StatCardComponent } from '../../shared/stat-card.component';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { FeedDagComponent, FeedRunStatusOverride } from './feed-dag.component';
import { SplitPaneComponent } from '../../shared/split-pane.component';
import { RunDetailCardComponent, RunDetailField, RunDetailItem } from '../../shared/run-detail-card.component';
import { RunFilter } from '../../shared/run-viewer.component';
import { CumulativePnlChartComponent, CumulativePnlPoint } from './charts/cumulative-pnl-chart.component';
import { TradePnlChartComponent } from './charts/trade-pnl-chart.component';
import { WinLossChartComponent } from './charts/win-loss-chart.component';
import { MonthlyPnlChartComponent, MonthlyPnlPoint } from './charts/monthly-pnl-chart.component';

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    FormsModule,
    LoadingSpinnerComponent,
    PanelTabsComponent,
    StatCardComponent,
    SchemaFormComponent,
    TradeTableComponent,
    FeedDagComponent,
    SplitPaneComponent,
    RunDetailCardComponent,
    CumulativePnlChartComponent,
    TradePnlChartComponent,
    WinLossChartComponent,
    MonthlyPnlChartComponent,
  ],
  templateUrl: './strategy-detail.component.html',
})
export class StrategyDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private toast = inject(ToastService);
  strategyService = inject(StrategyService);
  feedService = inject(FeedService);
  tradeService = inject(TradeService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);

  tabs = ['Performance', 'Universe', 'Runs', 'Feeds', 'Configuration'];
  activeTab = signal('Performance');
  page = signal(1);
  editing = signal(false);
  editedParameters = signal<Record<string, any>>({});
  feedDag = signal<StrategyFeedDAG | null>(null);

  // Runs tab state
  strategyRuns = signal<StrategyRunListItem[]>([]);
  runsTotal = signal(0);
  runsTotalPages = signal(0);
  runsPage = signal(1);
  selectedStrategyRun = signal<StrategyRunListItem | null>(null);
  runsFilterMode = signal<'none' | 'range' | 'around'>('none');
  runsRangeFrom = signal('');
  runsRangeTo = signal('');
  runsAroundDatetime = signal('');
  runsAroundRadius = signal<5 | 10 | 30 | 60>(5);
  runsRadiusOptions: (5 | 10 | 30 | 60)[] = [5, 10, 30, 60];

  selectedRunFeedStatuses = computed<Map<string, FeedRunStatusOverride> | null>(() => {
    const run = this.selectedStrategyRun();
    if (!run || run.feed_runs.length === 0) return null;
    const map = new Map<string, FeedRunStatusOverride>();
    for (const fr of run.feed_runs) {
      map.set(fr.feed_id, { status: fr.status, is_trigger: fr.is_trigger, feed_run_id: fr.feed_run_id });
    }
    return map;
  });

  strategyRunDetailItem = computed<RunDetailItem | null>(() => {
    const run = this.selectedStrategyRun();
    if (!run) return null;
    return {
      ...run,
      trigger: run.trigger_feed_id !== null ? `Feed #${run.trigger_feed_id}` : null,
      feed_count: run.feed_runs.length,
    };
  });

  strategyRunExtraFields: RunDetailField[] = [
    { label: 'Trigger', key: 'trigger' },
    { label: 'Feeds', key: 'feed_count' },
  ];

  // Chart computed data
  sortedTrades = computed(() => {
    return [...this.strategyService.allStrategyTrades()]
      .filter(t => t.entry_at !== null && t.current_status === 'CLOSED')
      .sort((a, b) => new Date(a.entry_at!).getTime() - new Date(b.entry_at!).getTime());
  });

  cumulativePnlData = computed<CumulativePnlPoint[]>(() => {
    const trades = this.sortedTrades();
    let cumulative = 0;
    return trades.map(t => {
      cumulative += (t.total_realized_pnl ?? 0);
      return { date: t.entry_at!, value: cumulative, symbol: t.display_symbol };
    });
  });

  monthlyPnlData = computed<MonthlyPnlPoint[]>(() => {
    const trades = this.sortedTrades();
    const monthMap = new Map<string, number>();
    for (const t of trades) {
      const d = new Date(t.entry_at!);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthMap.set(key, (monthMap.get(key) ?? 0) + (t.total_realized_pnl ?? 0));
    }
    return Array.from(monthMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, pnl]) => ({ month, pnl }));
  });

  wins = computed(() => this.sortedTrades().filter(t => (t.total_realized_pnl ?? 0) > 0).length);
  losses = computed(() => this.sortedTrades().filter(t => (t.total_realized_pnl ?? 0) < 0).length);
  breakeven = computed(() => this.sortedTrades().filter(t => (t.total_realized_pnl ?? 0) === 0).length);

  // Universe tab state
  universeItems = signal<UniverseItem[]>([]);
  showUniverseForm = signal(false);
  universeAddMode = signal<'individual' | 'group'>('individual');
  uniProviderId = '';
  uniFromAssetId = '';
  uniToAssetId = '';
  uniGroupId = '';

  strategyId = '';

  constructor() {}

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.strategyId) return;
      this.strategyId = id;

      // Reset state for the new strategy
      this.activeTab.set('Performance');
      this.page.set(1);
      this.editing.set(false);
      this.editedParameters.set({});
      this.feedDag.set(null);
      this.strategyRuns.set([]);
      this.runsTotal.set(0);
      this.runsTotalPages.set(0);
      this.runsPage.set(1);
      this.selectedStrategyRun.set(null);
      this.runsFilterMode.set('none');

      this.strategyService.loadStrategyDetail(this.strategyId);
      this.strategyService.loadStrategyTrades(this.strategyId);
      this.strategyService.loadAllStrategyTrades(this.strategyId);
      this.feedService.loadStrategyFeedDAG(this.strategyId).subscribe({
        next: (dag) => this.feedDag.set(dag),
      });
      this.loadStrategyRuns();
      this.loadUniverse();
      this.assetService.loadAssets();
      this.assetService.loadAssetGroups();
      this.providerService.loadProviders();
    });
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.strategyService.loadStrategyTrades(this.strategyId, newPage);
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

  selectStrategyRun(run: StrategyRunListItem): void {
    this.selectedStrategyRun.set(run);
  }

  onRunsPageChange(newPage: number): void {
    this.runsPage.set(newPage);
    this.loadStrategyRuns();
  }

  setRunsFilterMode(mode: 'none' | 'range' | 'around'): void {
    this.runsFilterMode.set(mode);
    if (mode === 'none') {
      this.runsRangeFrom.set('');
      this.runsRangeTo.set('');
      this.runsAroundDatetime.set('');
      this.runsPage.set(1);
      this.loadStrategyRuns();
    }
  }

  applyRunsFilter(): void {
    this.runsPage.set(1);
    this.selectedStrategyRun.set(null);
    this.loadStrategyRuns();
  }

  clearRunsFilter(): void {
    this.setRunsFilterMode('none');
  }

  runStatusClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'text-positive';
      case 'FAILED': return 'text-negative';
      case 'RUNNING': return 'text-warning';
      case 'PENDING': return 'text-fg-muted';
      default: return '';
    }
  }

  runStatusDotClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'bg-positive';
      case 'FAILED': return 'bg-negative';
      case 'RUNNING': return 'bg-warning animate-pulse';
      case 'PENDING': return 'bg-fg-faint';
      default: return 'bg-fg-faint';
    }
  }

  runDurationLabel(run: StrategyRunListItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  runsRadiusLabel(r: number): string {
    if (r < 60) return `${r}m`;
    return `${r / 60}h`;
  }

  // --- Universe tab methods ---

  loadUniverse(): void {
    this.strategyService.loadUniverse(this.strategyId).subscribe({
      next: items => this.universeItems.set(items),
    });
  }

  openUniverseForm(): void {
    this.uniProviderId = this.providerService.providers()[0]?.id ?? '';
    this.uniFromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.uniToAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.uniGroupId = '';
    this.universeAddMode.set('individual');
    this.showUniverseForm.set(true);
  }

  cancelUniverseForm(): void {
    this.showUniverseForm.set(false);
  }

  submitUniverseItem(): void {
    if (!this.uniProviderId || !this.uniFromAssetId || !this.uniToAssetId) return;
    const data: UniverseItemCreate = {
      provider_id: this.uniProviderId,
      from_asset_id: this.uniFromAssetId,
      to_asset_id: this.uniToAssetId,
      order: this.universeItems().length + 1,
    };
    this.strategyService.addUniverseItem(this.strategyId, data).subscribe({
      next: () => {
        this.toast.success('Asset added to universe');
        this.showUniverseForm.set(false);
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to add asset to universe'),
    });
  }

  addGroupToUniverse(): void {
    if (!this.uniGroupId) return;
    const group = this.assetService.assetGroups().find(g => g.id === this.uniGroupId);
    if (!group || group.members.length === 0) return;

    let completed = 0;
    const total = group.members.length;
    const startOrder = this.universeItems().length + 1;

    for (const member of group.members) {
      const data: UniverseItemCreate = {
        provider_id: member.provider_id,
        from_asset_id: member.from_asset_id,
        to_asset_id: member.to_asset_id,
        provider_asset_group_id: group.id,
        order: startOrder + member.order - 1,
      };
      this.strategyService.addUniverseItem(this.strategyId, data).subscribe({
        next: () => {
          completed++;
          if (completed === total) {
            this.toast.success(`Added ${total} assets from group`);
            this.showUniverseForm.set(false);
            this.loadUniverse();
          }
        },
        error: () => this.toast.error('Failed to add group member'),
      });
    }
  }

  removeUniverseItem(item: UniverseItem): void {
    this.strategyService.removeUniverseItem(
      this.strategyId, item.provider_id, item.from_asset_id, item.to_asset_id
    ).subscribe({
      next: () => {
        this.toast.success('Asset removed from universe');
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to remove asset'),
    });
  }

  private buildRunsFilter(): RunFilter | undefined {
    const mode = this.runsFilterMode();
    if (mode === 'range') {
      const f: RunFilter = {};
      if (this.runsRangeFrom()) f.started_after = new Date(this.runsRangeFrom()).toISOString();
      if (this.runsRangeTo()) f.started_before = new Date(this.runsRangeTo()).toISOString();
      if (f.started_after || f.started_before) return f;
    } else if (mode === 'around') {
      const dt = this.runsAroundDatetime();
      if (dt) {
        const center = new Date(dt);
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
