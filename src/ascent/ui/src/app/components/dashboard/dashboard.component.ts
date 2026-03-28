import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DashboardService } from '../../services/dashboard.service';
import { StrategyService } from '../../services/strategy.service';
import { TradeService } from '../../services/trade.service';
import { StatCardComponent } from '../shared/stat-card.component';
import { TradeTableComponent } from '../trade-table/trade-table.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../shared/empty-state.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, StatCardComponent, TradeTableComponent, Card, Skeleton, EmptyStateComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  dashboardService = inject(DashboardService);
  strategyService = inject(StrategyService);
  tradeService = inject(TradeService);

  ngOnInit(): void {
    this.dashboardService.loadStats();
    this.strategyService.loadStrategies();
    this.tradeService.loadTrades({ page: 1, page_size: 5 });
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-green-500' : 'text-red-500';
  }

  String = String;
}
