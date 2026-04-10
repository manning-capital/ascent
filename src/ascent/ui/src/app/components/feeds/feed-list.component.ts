import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { FeedService } from '../../services/feed.service';
import { FeedListItem } from '../../models/feed.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-feed-list',
  standalone: true,
  imports: [FormsModule, InputText, Select, Button, ServerTableComponent],
  templateUrl: './feed-list.component.html',
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

  private scheduleLabel(schedule: Record<string, any> | null): string {
    if (!schedule) return 'Triggered';
    const interval = schedule['interval'];
    if (!interval) return 'Triggered';
    if (interval < 60) return `${interval}s`;
    if (interval < 3600) return `${Math.round(interval / 60)}m`;
    if (interval < 86400) return `${Math.round(interval / 3600)}h`;
    return `${Math.round(interval / 86400)}d`;
  }

  columns: DataTableColumn<FeedListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'channel', header: 'Channel', cellType: 'monospace' },
    { field: 'schedule', header: 'Schedule', sortable: false, valueGetter: (p: any) => this.scheduleLabel(p.data?.schedule) },
    { field: 'total_runs', header: 'Total Runs', sortable: false },
    {
      field: 'last_run_status', header: 'Last Status', cellType: 'tag', sortable: false,
      tagMapper: (v: any) => {
        if (!v) return { label: 'N/A', severity: 'secondary' };
        const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
        return { label: v, severity: map[v] ?? 'secondary' };
      },
    },
    { field: 'last_run_at', header: 'Last Run', cellType: 'date', sortable: false },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112 },
  ];

  navigateToFeed = (row: any) => ['/feeds', row.id];

  fetchPage = computed<ServerFetchFn<FeedListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.feedService.loadFeedsPaginated(page, pageSize, filters, sort).pipe(
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
