import { Component, computed, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';
import { DashboardService } from '../../services/dashboard.service';
import { StrategyService } from '../../services/strategy.service';
import { TradeService } from '../../services/trade.service';
import { ApiService } from '../../services/api.service';
import { PaginatedResponse, TradeListItem } from '../../models/trade.model';
import type { ServerFetchFn } from '../shared/data-table/data-table.model';
import { StatCardComponent } from '../shared/stat-card.component';
import { TradeTableComponent } from '../trade-table/trade-table.component';
import { CumulativePnlChartComponent } from '../strategies/strategy-detail/charts/cumulative-pnl-chart.component';
import { WinLossChartComponent } from '../strategies/strategy-detail/charts/win-loss-chart.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../shared/empty-state.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, StatCardComponent, TradeTableComponent, CumulativePnlChartComponent, WinLossChartComponent, Card, Skeleton, EmptyStateComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  dashboardService = inject(DashboardService);
  strategyService = inject(StrategyService);
  tradeService = inject(TradeService);

  cumulativePnlData = computed(() => this.dashboardService.stats()?.cumulative_pnl ?? []);

  recentTradesFetchPage = computed<ServerFetchFn<TradeListItem>>(() => {
    return (page: number, pageSize: number) =>
      this.api.get<PaginatedResponse<TradeListItem>>('/trades', { page, page_size: 5, sort_field: 'entry_at', sort_order: 'desc' }).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
  });

  ngOnInit(): void {
    this.dashboardService.loadStats();
    this.strategyService.loadStrategies();
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-green-500' : 'text-red-500';
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
