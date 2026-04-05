import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { StrategyService } from '../../services/strategy.service';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-strategy-list',
  standalone: true,
  imports: [DataTableComponent],
  templateUrl: './strategy-list.component.html',
})
export class StrategyListComponent implements OnInit {
  private router = inject(Router);
  strategyService = inject(StrategyService);

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'strategy_type', header: 'Type', filterType: 'text' },
    { field: 'total_trades', header: 'Trades' },
    { field: 'win_rate', header: 'Win Rate', valueFormatter: (p) => p.value != null ? `${p.value}%` : '' },
    { field: 'open_trades', header: 'Open' },
    { field: 'total_pnl', header: 'Total P&L', cellType: 'currency' },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToStrategy = (row: any) => ['/strategies', row.id];

  ngOnInit(): void {
    this.strategyService.loadStrategies();
  }
}
