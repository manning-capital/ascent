import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { JsonPipe, KeyValuePipe } from '@angular/common';
import { map } from 'rxjs/operators';
import { ExchangeService } from '../../../services/exchange.service';
import { ToastService } from '../../../services/toast.service';
import { ApiService } from '../../../services/api.service';
import { OrderListItem } from '../../../models/order.model';
import { TradeListItem, PaginatedResponse } from '../../../models/trade.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';
import { ServerTableComponent } from '../../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../../shared/data-table/data-table.model';

@Component({
  selector: 'app-exchange-detail',
  standalone: true,
  imports: [
    RouterLink,
    JsonPipe,
    KeyValuePipe,
    Tabs, TabList, Tab,
    TradeTableComponent,
    Tag,
    Card,
    Skeleton,
    FieldPanelComponent,
    UniversePanelComponent,
    ServerTableComponent,
  ],
  templateUrl: './exchange-detail.component.html',
})
export class ExchangeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  private api = inject(ApiService);
  exchangeService = inject(ExchangeService);

  tabs = ['Overview', 'Orders', 'Trades', 'Universe', 'Configuration'];
  activeTab = signal('Overview');

  exchangeId = '';

  // Order columns
  orderColumns: DataTableColumn[] = [
    { field: 'instrument_name', header: 'Pair', sortable: false },
    { field: 'side', header: 'Side', cellType: 'tag', tagMapper: (v: string) => ({ label: v, severity: v === 'BUY' ? 'success' : v === 'SELL' ? 'danger' : 'secondary' }) },
    { field: 'order_type', header: 'Type', sortable: false, cellClass: 'text-muted-color' },
    { field: 'quantity', header: 'Qty' },
    { field: 'price', header: 'Price', valueFormatter: (p: any) => this.formatCurrency(p.value) },
    { field: 'filled_quantity', header: 'Filled', valueGetter: (p: any) => p.data?.filled_quantity !== null ? `${p.data.filled_quantity} / ${p.data.quantity}` : '\u2014' },
    { field: 'current_status', header: 'Status', sortable: false, cellType: 'tag', tagMapper: (v: string) => {
      if (!v) return { label: '', severity: 'secondary' };
      const map: Record<string, string> = { FILLED: 'success', PARTIALLY_FILLED: 'warn', SUBMITTED: 'warn', ACCEPTED: 'warn', REJECTED: 'danger', CANCELLED: 'secondary' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
  ];

  // Server-side fetch functions
  ordersFetchPage = computed<ServerFetchFn<OrderListItem> | null>(() => {
    this.exchangeService.selectedExchange(); // track exchange changes
    const id = this.exchangeId;
    if (!id) return null;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<OrderListItem>>(`/exchanges/${id}/orders`, params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  tradesFetchPage = computed<ServerFetchFn<TradeListItem> | null>(() => {
    this.exchangeService.selectedExchange(); // track exchange changes
    const id = this.exchangeId;
    if (!id) return null;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<TradeListItem>>(`/exchanges/${id}/trades`, params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  stats = computed(() => this.exchangeService.exchangeStats());

  generalFields = computed<PanelField[]>(() => {
    const exchange = this.exchangeService.selectedExchange();
    if (!exchange) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: exchange.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: exchange.display_name },
      { type: 'text', key: 'type', label: 'Type', value: exchange.exchange_type_name, fallback: '--' },
      { type: 'link', key: 'instrumentType', label: 'Instrument Type', value: exchange.instrument_type_name, route: exchange.instrument_type_id ? ['/settings/instrument-types', exchange.instrument_type_id] : [], fallback: 'Any' },
      { type: 'link', key: 'provider', label: 'Provider', value: exchange.provider_name, route: exchange.provider_id ? ['/settings/providers', exchange.provider_id] : [], fallback: 'None' },
      { type: 'active', key: 'isActive', label: 'Active', value: exchange.is_active },
      { type: 'date', key: 'created', label: 'Created', value: exchange.created_at },
      { type: 'text', key: 'description', label: 'Description', value: exchange.description },
    ];
  });

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.exchangeId) return;
      this.exchangeId = id;

      // Restore tab from query params
      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Overview');
      }

      this.exchangeService.loadExchangeDetail(this.exchangeId);
      this.exchangeService.loadExchangeStats(this.exchangeId);
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.updateQueryParams({ tab });
  }

  private updateQueryParams(params: Record<string, string | null>): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: params,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  skeletonRows(count: number): number[] {
    return Array.from({ length: count }, (_, i) => i);
  }

  formatCurrency(value: number | null): string {
    if (value === null || value === undefined) return '\u2014';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
  }

  formatNumber(value: number | null): string {
    if (value === null || value === undefined) return '\u2014';
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value);
  }

  pnlClass(value: number | null): string {
    if (value === null || value === undefined || value === 0) return '';
    return value > 0 ? 'text-positive' : 'text-negative';
  }

  // --- Universe tab methods ---

  onAddInstruments(event: { instrumentIds: string[]; startOrder: number }): void {
    this.exchangeService.batchAddInstruments(this.exchangeId, event.instrumentIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.instrumentIds.length} instrument(s) added to universe`);
      },
      error: () => this.toast.error('Failed to add instruments to universe'),
    });
  }

  removeUniverseItem(instrumentId: string): void {
    this.exchangeService.removeUniverseItem(this.exchangeId, instrumentId).subscribe({
      next: () => {
        this.toast.success('Instrument removed from universe');
      },
      error: () => this.toast.error('Failed to remove instrument'),
    });
  }

  onAddComposites(event: { compositeIds: string[]; startOrder: number }): void {
    this.exchangeService.batchAddComposites(this.exchangeId, event.compositeIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.compositeIds.length} composite(s) added to universe`);
      },
      error: () => this.toast.error('Failed to add composites to universe'),
    });
  }

  removeCompositeItem(compositeId: string): void {
    this.exchangeService.removeCompositeUniverseItem(this.exchangeId, compositeId).subscribe({
      next: () => {
        this.toast.success('Composite removed from universe');
      },
      error: () => this.toast.error('Failed to remove composite'),
    });
  }
}
