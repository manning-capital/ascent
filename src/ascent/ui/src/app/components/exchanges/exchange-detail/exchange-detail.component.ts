import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { JsonPipe, KeyValuePipe } from '@angular/common';
import { map } from 'rxjs/operators';
import { ExchangeService } from '../../../services/exchange.service';
import { ApiService } from '../../../services/api.service';
import { OrderListItem } from '../../../models/order.model';
import { Instrument } from '../../../models/asset.model';
import { TradeListItem, PaginatedResponse } from '../../../models/trade.model';
import { SelectButton } from 'primeng/selectbutton';
import { FormsModule } from '@angular/forms';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { TradeTableComponent } from '../../trade-table/trade-table.component';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../../ui/data-table/app-column.model';
import { AppPageHeaderComponent } from '../../ui/page-header/app-page-header.component';

const CURRENCY_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
});
const NUMBER_FORMATTER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 });

@Component({
  selector: 'app-exchange-detail',
  standalone: true,
  imports: [
    JsonPipe,
    KeyValuePipe,
    Tabs, TabList, Tab,
    TradeTableComponent,
    Tag,
    Card,
    Skeleton,
    FieldPanelComponent,
    AppDataTableComponent,
    SelectButton,
    FormsModule,
    AppPageHeaderComponent,
  ],
  templateUrl: './exchange-detail.component.html',
})
export class ExchangeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(ApiService);
  exchangeService = inject(ExchangeService);

  tabs = ['Overview', 'Orders', 'Trades', 'Universe', 'Configuration'];
  activeTab = signal('Overview');

  exchangeId = '';

  // Order columns
  orderColumns: AppColumn<OrderListItem>[] = [
    { field: 'instrument_name', header: 'Pair', sortable: false },
    {
      field: 'side', header: 'Side', cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: (v === 'BUY' ? 'success' : v === 'SELL' ? 'danger' : 'secondary') as AppSeverity,
      }),
    },
    { field: 'order_type', header: 'Type', sortable: false, cellClass: 'text-fg-muted' },
    { field: 'quantity', header: 'Qty' },
    { field: 'price', header: 'Price', format: (v) => this.formatCurrency(v) },
    {
      field: 'filled_quantity', header: 'Filled',
      format: (_, row) => row?.filled_quantity !== null ? `${row.filled_quantity} / ${row.quantity}` : '\u2014',
    },
    {
      field: 'current_status', header: 'Status', sortable: false, cellType: 'tag',
      tagMapper: (v: string) => {
        if (!v) return { label: '', severity: 'secondary' as AppSeverity };
        const map: Record<string, AppSeverity> = {
          FILLED: 'success', PARTIALLY_FILLED: 'warn', SUBMITTED: 'warn',
          ACCEPTED: 'warn', REJECTED: 'danger', CANCELLED: 'secondary',
        };
        return { label: v, severity: map[v] ?? 'secondary' };
      },
    },
  ];

  // Server-side fetch functions
  ordersFetchPage = computed<AppFetchFn<OrderListItem> | null>(() => {
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

  tradesFetchPage = computed<AppFetchFn<TradeListItem> | null>(() => {
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
    return CURRENCY_FORMATTER.format(value);
  }

  formatNumber(value: number | null): string {
    if (value === null || value === undefined) return '\u2014';
    return NUMBER_FORMATTER.format(value);
  }

  pnlClass(value: number | null): string {
    if (value === null || value === undefined || value === 0) return '';
    return value > 0 ? 'text-positive' : 'text-negative';
  }

  // --- Universe tab (read-only, implicit from provider + instrument type) ---

  universeMode = signal<'instruments' | 'composites'>('instruments');
  universeModeOptions = [
    { label: 'Instruments', value: 'instruments' },
    { label: 'Composites', value: 'composites' },
  ];

  instrumentColumns: AppColumn[] = [
    { field: 'display_name', header: 'Instrument', sortable: true },
    { field: 'name', header: 'Name', sortable: true, cellClass: 'font-mono text-fg-muted' },
    {
      field: 'is_active', header: 'Status', sortable: false, cellType: 'tag',
      tagMapper: (v: boolean) => ({ label: v ? 'Active' : 'Inactive', severity: (v ? 'success' : 'secondary') as AppSeverity }),
    },
  ];

  compositeColumns: AppColumn[] = [
    { field: 'display_name', header: 'Composite', sortable: true },
    { field: 'name', header: 'Name', sortable: true, cellClass: 'font-mono text-fg-muted' },
    {
      field: 'is_active', header: 'Status', sortable: false, cellType: 'tag',
      tagMapper: (v: boolean) => ({ label: v ? 'Active' : 'Inactive', severity: (v ? 'success' : 'secondary') as AppSeverity }),
    },
  ];

  instrumentsFetchPage = computed<AppFetchFn<Instrument> | null>(() => {
    const exchange = this.exchangeService.selectedExchange();
    this.universeMode(); // track mode changes
    if (!exchange || !exchange.provider_id || !exchange.instrument_type_id) return null;
    const providerId = exchange.provider_id;
    const instrumentTypeId = exchange.instrument_type_id;
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = {
        page, page_size: pageSize,
        provider_id: providerId,
        instrument_type_id: instrumentTypeId,
      };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<Instrument>>('/instruments/search', params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  compositesFetchPage = computed<AppFetchFn<any> | null>(() => {
    const exchange = this.exchangeService.selectedExchange();
    this.universeMode(); // track mode changes
    if (!exchange) return null;
    // For composites, we don't have a direct provider+type filter on composites/search.
    // Show all composites for now — the strategy-level validation enforces tradeability.
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
      return this.api.get<PaginatedResponse<any>>('/composites/search', params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });
}
