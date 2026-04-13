import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { StrategyService } from '../../services/strategy.service';
import { StrategyListItem } from '../../models/strategy.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-strategy-list',
  standalone: true,
  imports: [FormsModule, InputText, Select, Button, ServerTableComponent],
  templateUrl: './strategy-list.component.html',
})
export class StrategyListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private strategyService = inject(StrategyService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  columns: DataTableColumn<StrategyListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'total_trades', header: 'Trades', sortable: false },
    { field: 'win_rate', header: 'Win Rate', sortable: false, valueFormatter: (p) => p.value != null ? `${p.value}%` : '' },
    { field: 'open_trades', header: 'Open', sortable: false },
    { field: 'total_pnl', header: 'Total P&L', cellType: 'currency', sortable: false },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112 },
  ];

  navigateToStrategy = (row: any) => ['/strategies', row.id];

  fetchPage = computed<ServerFetchFn<StrategyListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.strategyService.loadStrategiesPaginated(page, pageSize, filters, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    if (qp.get('search')) this.search.set(qp.get('search')!);
    if (qp.get('is_active') != null) this.statusFilter.set(qp.get('is_active') === 'true');
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.updateUrl();
  }

  onStatusChange(value: boolean | null): void {
    this.statusFilter.set(value);
    this.updateUrl();
  }

  clearFilters(): void {
    this.search.set('');
    this.statusFilter.set(null);
    this.updateUrl();
  }

  private updateUrl(): void {
    const queryParams: Record<string, any> = {};
    const search = this.search();
    if (search) queryParams['search'] = search;
    const isActive = this.statusFilter();
    if (isActive != null) queryParams['is_active'] = isActive;
    this.router.navigate([], { relativeTo: this.route, queryParams, replaceUrl: true });
  }
}
