import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ExchangeService } from '../../services/exchange.service';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-exchange-list',
  standalone: true,
  imports: [DataTableComponent],
  templateUrl: './exchange-list.component.html',
})
export class ExchangeListComponent implements OnInit {
  private router = inject(Router);
  exchangeService = inject(ExchangeService);

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'name', header: 'Name', cellType: 'monospace', filterType: 'text' },
    { field: 'exchange_type_name', header: 'Type', filterType: 'text' },
    { field: 'instrument_type_name', header: 'Instrument Type', cellType: 'link', linkRoute: (row: any) => row.instrument_type_id ? `/settings/instrument-types/${row.instrument_type_id}` : null, filterType: 'text', valueFormatter: (p: any) => p.value || 'Any' },
    { field: 'provider_name', header: 'Provider', cellType: 'link', linkRoute: (row: any) => row.provider_id ? `/settings/providers/${row.provider_id}` : null, filterType: 'text', valueFormatter: (p: any) => p.value || 'None' },
    { field: 'created_at', header: 'Created', cellType: 'date' },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToExchange = (row: any) => ['/exchanges', row.id];

  ngOnInit(): void {
    this.exchangeService.loadExchanges();
  }
}
