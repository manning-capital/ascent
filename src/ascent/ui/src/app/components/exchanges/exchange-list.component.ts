import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { ExchangeService } from '../../services/exchange.service';
import { ExchangeListItem } from '../../models/exchange.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-exchange-list',
  standalone: true,
  imports: [FormsModule, InputText, Select, Button, ServerTableComponent],
  templateUrl: './exchange-list.component.html',
})
export class ExchangeListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private exchangeService = inject(ExchangeService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  columns: DataTableColumn<ExchangeListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'instrument_type_name', header: 'Instrument Type', cellType: 'link', linkRoute: (row: any) => row.instrument_type_id ? `/settings/instrument-types/${row.instrument_type_id}` : null, valueFormatter: (p: any) => p.value || 'Any' },
    { field: 'provider_name', header: 'Provider', cellType: 'link', linkRoute: (row: any) => row.provider_id ? `/settings/providers/${row.provider_id}` : null, valueFormatter: (p: any) => p.value || 'None' },
    { field: 'created_at', header: 'Created', cellType: 'date' },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112 },
  ];

  navigateToExchange = (row: any) => ['/exchanges', row.id];

  fetchPage = computed<ServerFetchFn<ExchangeListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.exchangeService.loadExchangesPaginated(page, pageSize, filters, sort).pipe(
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
