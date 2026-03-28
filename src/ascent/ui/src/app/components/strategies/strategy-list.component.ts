import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { StrategyService } from '../../services/strategy.service';
import { TradeService } from '../../services/trade.service';
import { StatCardComponent } from '../shared/stat-card.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../shared/empty-state.component';

@Component({
  selector: 'app-strategy-list',
  standalone: true,
  imports: [RouterLink, StatCardComponent, Card, Skeleton, EmptyStateComponent],
  templateUrl: './strategy-list.component.html',
})
export class StrategyListComponent implements OnInit {
  strategyService = inject(StrategyService);
  tradeService = inject(TradeService);

  ngOnInit(): void {
    this.strategyService.loadStrategies();
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-green-500' : 'text-red-500';
  }
}
