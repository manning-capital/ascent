import { Component, input, output, inject } from '@angular/core';
import { Router } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { TableModule } from 'primeng/table';
import { TradeListItem, TradeLegSummary } from '../../models/trade.model';
import { TradeService } from '../../services/trade.service';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';

@Component({
  selector: 'app-trade-table',
  standalone: true,
  imports: [BadgeComponent, DecimalPipe, StatCardComponent, TableModule],
  templateUrl: './trade-table.component.html',
})
export class TradeTableComponent {
  private router = inject(Router);
  tradeService = inject(TradeService);

  trades = input.required<TradeListItem[]>();
  showStrategy = input(true);
  page = input(1);
  totalPages = input(1);
  pageChange = output<number>();

  navigateToTrade(tradeId: string): void {
    this.router.navigate(['/trades', tradeId]);
  }

  onPageChange(newPage: number): void {
    this.pageChange.emit(newPage);
  }

  getMainLeg(trade: TradeListItem): TradeLegSummary | null {
    return trade.legs.length > 0 ? trade.legs[0] : null;
  }
}
