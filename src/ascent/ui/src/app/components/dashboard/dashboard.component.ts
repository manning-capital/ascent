import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { auditTime, map } from 'rxjs/operators';
import { DashboardService } from '../../services/dashboard.service';
import { StrategyService } from '../../services/strategy.service';
import { TradeService } from '../../services/trade.service';
import { TradeStreamService } from '../../services/trade-stream.service';
import { ApiService } from '../../services/api.service';
import { PaginatedResponse, TradeListItem } from '../../models/trade.model';
import type { AppFetchFn } from '../ui/data-table/app-column.model';
import { AppStatCardComponent } from '../ui/stat-card/app-stat-card.component';
import { TradeTableComponent } from '../trade-table/trade-table.component';
import { CumulativePnlChartComponent, Lookback, LOOKBACK_OPTIONS } from '../strategies/strategy-detail/charts/cumulative-pnl-chart.component';
import { WinLossChartComponent } from '../strategies/strategy-detail/charts/win-loss-chart.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { SelectButton } from 'primeng/selectbutton';
import { AppEmptyStateComponent } from '../ui/empty-state/app-empty-state.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';

const CURRENCY_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
});

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, FormsModule, AppStatCardComponent, TradeTableComponent, CumulativePnlChartComponent, WinLossChartComponent, Card, Skeleton, SelectButton, AppEmptyStateComponent, AppPageHeaderComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit, OnDestroy {
  pnlLookback = signal<Lookback>('all');
  lookbackOptions = LOOKBACK_OPTIONS;
  private streamSvc = inject(TradeStreamService);
  private streamSub: Subscription | null = null;
  private static readonly REFRESH_AUDIT_MS = 3000;

  private api = inject(ApiService);
  dashboardService = inject(DashboardService);
  strategyService = inject(StrategyService);
  tradeService = inject(TradeService);

  cumulativePnlData = computed(() => this.dashboardService.stats()?.cumulative_pnl ?? []);

  recentTradesFetchPage = computed<AppFetchFn<TradeListItem>>(() => {
    return (page: number, pageSize: number, sort?: { field: string; order: string }) =>
      this.api.get<PaginatedResponse<TradeListItem>>('/trades', { page, page_size: 5, sort_field: sort?.field ?? 'entry_at', sort_order: sort?.order ?? 'desc' }).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
  });

  ngOnInit(): void {
    this.dashboardService.loadStats();
    this.strategyService.loadStrategies();

    this.streamSvc.connect();
    this.streamSub = this.streamSvc.tradeUpdates$
      .pipe(auditTime(DashboardComponent.REFRESH_AUDIT_MS))
      .subscribe(() => this.dashboardService.refreshStats());
  }

  ngOnDestroy(): void {
    this.streamSub?.unsubscribe();
  }

  formatCurrency(value: number): string {
    return CURRENCY_FORMATTER.format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-positive' : 'text-negative';
  }

  formatDuration(seconds: number | null): string {
    if (seconds == null) return '-';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
    return `${(seconds / 86400).toFixed(1)}d`;
  }

  relativeTime(dateStr: string | null): string {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  String = String;
}
