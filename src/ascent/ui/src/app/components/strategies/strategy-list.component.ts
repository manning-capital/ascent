import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { DataView, DataViewLazyLoadEvent } from 'primeng/dataview';
import { StrategyService } from '../../services/strategy.service';
import { StrategyListItem } from '../../models/strategy.model';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import { AppEmptyStateComponent } from '../ui/empty-state/app-empty-state.component';
import { AppStatusDotComponent } from '../ui/cells/app-status-dot.component';
import { AppProgressBarComponent } from '../ui/cells/app-progress-bar.component';
import { AppRelativeTimeComponent } from '../ui/cells/app-relative-time.component';
import type { AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination';
import type { Observable } from 'rxjs';

@Component({
  selector: 'app-strategy-list',
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
    AppProgressBarComponent,
    AppRelativeTimeComponent,
  ],
  templateUrl: './strategy-list.component.html',
  host: { class: 'flex flex-col h-full min-h-0' },
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

  items = signal<StrategyListItem[]>([]);
  total = signal(0);
  first = signal(0);
  pageSize = signal(DEFAULT_PAGE_SIZE);
  loading = signal(false);

  fetchPage = computed<AppFetchFn<StrategyListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.strategyService.loadStrategiesPaginated(page, pageSize, filters, sort as any).pipe(
        map((res) => ({ items: res.items, total: res.total })),
      ) as ReturnType<AppFetchFn<StrategyListItem>>;
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

  navigateToStrategy(row: StrategyListItem): void {
    this.router.navigate(['/strategies', row.id]);
  }

  pnlClass(value: number | null | undefined): string {
    if (value == null || value === 0) return 'text-fg-muted';
    return value > 0 ? 'text-positive' : 'text-negative';
  }

  winRateSeverity(rate: number | null | undefined): AppSeverity {
    if (rate == null) return 'secondary';
    if (rate >= 60) return 'success';
    if (rate >= 45) return 'warn';
    return 'danger';
  }

  formatPnl(value: number | null | undefined): string {
    if (value == null) return '—';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toLocaleString(undefined, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    })}`;
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
