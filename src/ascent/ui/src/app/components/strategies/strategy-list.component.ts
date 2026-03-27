import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { StrategyService } from '../../services/strategy.service';
import { TradeService } from '../../services/trade.service';
import { LoadingSpinnerComponent } from '../shared/loading-spinner.component';
import { StatCardComponent } from '../shared/stat-card.component';

@Component({
  selector: 'app-strategy-list',
  standalone: true,
  imports: [RouterLink, LoadingSpinnerComponent, StatCardComponent],
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
    return value > 0 ? 'text-positive' : 'text-negative';
  }
}
