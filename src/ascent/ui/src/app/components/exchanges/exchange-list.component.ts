import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { DataView, DataViewLazyLoadEvent } from 'primeng/dataview';
import { ExchangeService } from '../../services/exchange.service';
import { ExchangeListItem } from '../../models/exchange.model';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import { AppEmptyStateComponent } from '../ui/empty-state/app-empty-state.component';
import { AppStatusDotComponent } from '../ui/cells/app-status-dot.component';
import { AppRelativeTimeComponent } from '../ui/cells/app-relative-time.component';
import type { AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination';

@Component({
  selector: 'app-exchange-list',
  standalone: true,
  imports: [
    FormsModule,
    InputText,
    Select,
    Button,
    DataView,
    AppPageHeaderComponent,
    AppEmptyStateComponent,
    AppStatusDotComponent,
    AppRelativeTimeComponent,
  ],
  templateUrl: './exchange-list.component.html',
  host: { class: 'flex flex-col h-full min-h-0' },
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

  items = signal<ExchangeListItem[]>([]);
  total = signal(0);
  first = signal(0);
  pageSize = signal(DEFAULT_PAGE_SIZE);
  loading = signal(false);

  fetchPage = computed<AppFetchFn<ExchangeListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.exchangeService
        .loadExchangesPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total }))) as ReturnType<AppFetchFn<ExchangeListItem>>;
    };
  });

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    if (qp.get('search')) this.search.set(qp.get('search')!);
    if (qp.get('is_active') != null) this.statusFilter.set(qp.get('is_active') === 'true');
    this.load();
  }

  onLazyLoad(event: DataViewLazyLoadEvent): void {
    if (event.first != null) this.first.set(event.first);
    if (event.rows != null) this.pageSize.set(event.rows);
    this.load();
  }

  private load(): void {
    const page = Math.floor(this.first() / this.pageSize()) + 1;
    this.loading.set(true);
    this.fetchPage()(page, this.pageSize()).subscribe({
      next: (res) => {
        this.items.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  navigateToExchange(row: ExchangeListItem): void {
    this.router.navigate(['/exchanges', row.id]);
  }

  dotSeverity(row: ExchangeListItem): AppSeverity {
    return row.is_active ? 'success' : 'secondary';
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.first.set(0);
    this.load();
    this.updateUrl();
  }

  onStatusChange(value: boolean | null): void {
    this.statusFilter.set(value);
    this.first.set(0);
    this.load();
    this.updateUrl();
  }

  clearFilters(): void {
    this.search.set('');
    this.statusFilter.set(null);
    this.first.set(0);
    this.load();
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
