import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FeedService } from '../../services/feed.service';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-feed-list',
  standalone: true,
  imports: [DataTableComponent],
  templateUrl: './feed-list.component.html',
})
export class FeedListComponent implements OnInit {
  private router = inject(Router);
  feedService = inject(FeedService);

  private scheduleLabel(schedule: Record<string, any> | null): string {
    if (!schedule) return 'Triggered';
    const interval = schedule['interval'];
    if (!interval) return 'Triggered';
    if (interval < 60) return `${interval}s`;
    if (interval < 3600) return `${Math.round(interval / 60)}m`;
    if (interval < 86400) return `${Math.round(interval / 3600)}h`;
    return `${Math.round(interval / 86400)}d`;
  }

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'channel', header: 'Channel', cellType: 'monospace', filterType: 'text' },
    { field: 'schedule', header: 'Schedule', sortable: false, valueGetter: (p: any) => this.scheduleLabel(p.data?.schedule) },
    { field: 'total_runs', header: 'Total Runs' },
    {
      field: 'last_run_status', header: 'Last Status', cellType: 'tag',
      tagMapper: (v: any) => {
        if (!v) return { label: 'N/A', severity: 'secondary' };
        const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
        return { label: v, severity: map[v] ?? 'secondary' };
      },
    },
    { field: 'last_run_at', header: 'Last Run', cellType: 'date' },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToFeed = (row: any) => ['/feeds', row.id];

  ngOnInit(): void {
    this.feedService.loadFeeds();
  }
}
