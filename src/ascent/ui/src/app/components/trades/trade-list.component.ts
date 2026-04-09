import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { SelectButton } from 'primeng/selectbutton';
import { StrategyService } from '../../services/strategy.service';
import { ApiService } from '../../services/api.service';
import { PaginatedResponse, TradeListItem } from '../../models/trade.model';
import { ServerFetchFn } from '../shared/data-table/data-table.model';
import { TradeTableComponent } from '../trade-table/trade-table.component';

@Component({
  selector: 'app-trade-list',
  standalone: true,
  imports: [FormsModule, Select, DatePicker, InputText, Card, Button, SelectButton, TradeTableComponent],
  templateUrl: './trade-list.component.html',
})
export class TradeListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(ApiService);
  strategyService = inject(StrategyService);

  search = signal('');
  status = signal('');
  selectedStrategyId = signal<number | null>(null);
  selectedTags = signal<string[]>([]);
  startDate = signal<Date | null>(null);
  endDate = signal<Date | null>(null);
  page = signal(1);
  pageSize = signal(25);
  sortField = signal('entry_at');
  sortOrder = signal('desc');

  private isSyncingFromUrl = false;

  availableTags = ['LONG', 'SHORT', 'COMPOUND', 'PAPER'];
  statusOptions = [
    { label: 'Pending', value: 'PENDING' },
    { label: 'Opening', value: 'OPENING' },
    { label: 'Open', value: 'OPEN' },
    { label: 'Closing', value: 'CLOSING' },
    { label: 'Closed', value: 'CLOSED' },
    { label: 'Cancelled', value: 'CANCELLED' },
    { label: 'Error', value: 'ERROR' },
  ];

  fetchPageFn = computed<ServerFetchFn<TradeListItem>>(() => {
    const search = this.search();
    const status = this.status();
    const strategyId = this.selectedStrategyId();
    const tags = this.selectedTags();
    const startDate = this.startDate();
    const endDate = this.endDate();
    const sortField = this.sortField();
    const sortOrder = this.sortOrder();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
        sort_field: sort?.field ?? sortField,
        sort_order: sort?.order ?? sortOrder,
      };
      if (search) params['search'] = search;
      if (status) params['status'] = status;
      if (strategyId) params['strategy_id'] = strategyId;
      if (tags.length) params['tags'] = tags;
      if (startDate) params['start_date'] = startDate.toISOString().split('T')[0];
      if (endDate) params['end_date'] = endDate.toISOString().split('T')[0];
      return this.api.get<PaginatedResponse<TradeListItem>>('/trades', params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  ngOnInit(): void {
    this.strategyService.loadStrategies();
    const qp = this.route.snapshot.queryParamMap;
    this.isSyncingFromUrl = true;
    if (qp.get('search')) this.search.set(qp.get('search')!);
    if (qp.get('status')) this.status.set(qp.get('status')!);
    if (qp.get('strategy_id')) this.selectedStrategyId.set(Number(qp.get('strategy_id')));
    if (qp.get('tags')) {
      const tags = qp.getAll('tags');
      this.selectedTags.set(tags);
    }
    if (qp.get('start_date')) this.startDate.set(new Date(qp.get('start_date')! + 'T00:00:00'));
    if (qp.get('end_date')) this.endDate.set(new Date(qp.get('end_date')! + 'T00:00:00'));
    if (qp.get('page')) this.page.set(parseInt(qp.get('page')!, 10) || 1);
    if (qp.get('page_size')) this.pageSize.set(parseInt(qp.get('page_size')!, 10) || 25);
    if (qp.get('sort_field')) this.sortField.set(qp.get('sort_field')!);
    if (qp.get('sort_order')) this.sortOrder.set(qp.get('sort_order')!);
    this.isSyncingFromUrl = false;
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.page.set(1);
    this.updateUrl();
  }

  onStatusChange(value: string | null): void {
    this.status.set(value ?? '');
    this.page.set(1);
    this.updateUrl();
  }

  onStrategyChange(value: number | null): void {
    this.selectedStrategyId.set(value);
    this.page.set(1);
    this.updateUrl();
  }

  onDateChange(): void {
    this.page.set(1);
    this.updateUrl();
  }

  onTagsChange(tags: string[]): void {
    this.selectedTags.set(tags);
    this.page.set(1);
    this.updateUrl();
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.updateUrl();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
    this.updateUrl();
  }

  onSortChange(sort: { field: string; order: string }): void {
    this.sortField.set(sort.field);
    this.sortOrder.set(sort.order);
    this.page.set(1);
    this.updateUrl();
  }

  clearFilters(): void {
    this.search.set('');
    this.status.set('');
    this.selectedStrategyId.set(null);
    this.selectedTags.set([]);
    this.startDate.set(null);
    this.endDate.set(null);
    this.page.set(1);
    this.updateUrl();
  }

  private updateUrl(): void {
    const queryParams: Record<string, any> = {
      page: this.page(),
      page_size: this.pageSize(),
      sort_field: this.sortField(),
      sort_order: this.sortOrder(),
    };
    const search = this.search();
    if (search) queryParams['search'] = search;
    const status = this.status();
    if (status) queryParams['status'] = status;
    const strategyId = this.selectedStrategyId();
    if (strategyId) queryParams['strategy_id'] = strategyId;
    const tags = this.selectedTags();
    if (tags.length) queryParams['tags'] = tags;
    const startDate = this.startDate();
    if (startDate) queryParams['start_date'] = startDate.toISOString().split('T')[0];
    const endDate = this.endDate();
    if (endDate) queryParams['end_date'] = endDate.toISOString().split('T')[0];

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }
}
