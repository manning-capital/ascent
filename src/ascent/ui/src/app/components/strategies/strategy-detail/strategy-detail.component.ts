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
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { StrategyRunsTabComponent } from './strategy-runs-tab.component';
import { CumulativePnlChartComponent, CumulativePnlPoint } from './charts/cumulative-pnl-chart.component';
import { PnlDistributionChartComponent } from './charts/pnl-distribution-chart.component';
import { Button } from 'primeng/button';

import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';

import { ServerTableComponent } from '../../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../../shared/data-table/data-table.model';

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
    Tag,
    Card,
    Skeleton,
    UniversePanelComponent,
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

  tabs = ['Overview', 'Trades', 'Orders', 'Universe', 'Runs', 'Configuration'];
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
      this.editing.set(false);
      this.editedParameters.set({});
      this.feedDag.set(null);

      this.strategyService.loadStrategyDetail(this.strategyId);
      this.strategyService.loadStrategyStats(this.strategyId);
      this.feedService.loadStrategyFeedDAG(this.strategyId).subscribe({
        next: (dag) => this.feedDag.set(dag),
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
    this.strategyService.removeUniverseItem(this.strategyId, instrumentId).subscribe({
      next: () => {
        this.toast.success('Instrument removed from universe');
      },
      error: () => this.toast.error('Failed to remove instrument'),
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
    this.strategyService.removeCompositeUniverseItem(this.strategyId, compositeId).subscribe({
      next: () => {
        this.toast.success('Composite removed from universe');
      },
      error: () => this.toast.error('Failed to remove composite'),
    });
  }

}
