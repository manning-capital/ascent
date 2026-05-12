import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { DataView, DataViewLazyLoadEvent } from 'primeng/dataview';
import { FeedService } from '../../services/feed.service';
import { FeedListItem } from '../../models/feed.model';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import { AppEmptyStateComponent } from '../ui/empty-state/app-empty-state.component';
import { AppStatusDotComponent } from '../ui/cells/app-status-dot.component';
import { AppRelativeTimeComponent } from '../ui/cells/app-relative-time.component';
import { AppRunHistoryComponent } from '../ui/cells/app-run-history.component';
import type { AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination';

@Component({
  selector: 'app-feed-list',
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
    AppRunHistoryComponent,
  ],
  templateUrl: './feed-list.component.html',
  host: { class: 'flex flex-col h-full min-h-0' },
})
export class FeedListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private feedService = inject(FeedService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  items = signal<FeedListItem[]>([]);
  total = signal(0);
  first = signal(0);
  pageSize = signal(DEFAULT_PAGE_SIZE);
  loading = signal(false);

  fetchPage = computed<AppFetchFn<FeedListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.feedService
        .loadFeedsPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total }))) as ReturnType<AppFetchFn<FeedListItem>>;
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

  navigateToFeed(row: FeedListItem): void {
    this.router.navigate(['/feeds', row.id]);
  }

  scheduleLabel(schedule: Record<string, any> | null | undefined): string {
    if (!schedule) return 'Triggered';
    const interval = schedule['interval'];
    if (!interval) return 'Triggered';
    if (interval < 60) return `${interval}s`;
    if (interval < 3600) return `${Math.round(interval / 60)}m`;
    if (interval < 86400) return `${Math.round(interval / 3600)}h`;
    return `${Math.round(interval / 86400)}d`;
  }

  runStatusSeverity(status: string | null | undefined): AppSeverity {
    if (!status) return 'secondary';
    const map: Record<string, AppSeverity> = {
      COMPLETED: 'success',
      SUCCEEDED: 'success',
      FAILED: 'danger',
      ERROR: 'danger',
      RUNNING: 'info',
      PENDING: 'warn',
    };
    return map[status] ?? 'secondary';
  }

  feedDotSeverity(row: FeedListItem): AppSeverity {
    if (!row.is_active) return 'secondary';
    if (row.last_run_status === 'FAILED' || row.last_run_status === 'ERROR') return 'danger';
    if (row.last_run_status === 'RUNNING') return 'info';
    return 'success';
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
