import { Component, computed, inject, input, signal } from '@angular/core';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import type { AppColumn, AppFetchFn, AppSeverity } from '../../ui/data-table/app-column.model';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import { RunFilterPanelComponent } from '../../shared/run-filter-panel.component';
import type { RunFilter } from '../../shared/run-viewer.component';

const STATUS_SEVERITY: Record<string, AppSeverity> = {
  COMPLETED: 'success',
  FAILED: 'danger',
  RUNNING: 'warn',
};

@Component({
  selector: 'app-feed-runs-tab',
  standalone: true,
  imports: [AppDataTableComponent, RunFilterPanelComponent],
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }
  `],
  template: `
    <div class="p-6 flex flex-col flex-1 min-h-0 gap-4">
      <app-run-filter-panel class="shrink-0" (filterChange)="onFilterChange($event)"/>

      <app-data-table class="flex-1 min-h-0"
        [columns]="runColumns"
        [fetchPage]="fetchPage()"
        [rowClickRoute]="navigateToRun()"
        emptyMessage="No runs yet."/>
    </div>
  `,
})
export class FeedRunsTabComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();

  private filter = signal<RunFilter>({});

  runColumns: AppColumn<FeedRunListItem>[] = [
    {
      field: 'status', header: 'Status', cellType: 'tag', width: 96,
      tagMapper: (v: string) => ({ label: v, severity: STATUS_SEVERITY[v] ?? 'secondary' }),
    },
    { field: 'id', header: 'Run ID', cellType: 'monospace', sortable: false },
    { field: 'started_at', header: 'Started', cellType: 'date' },
    { field: 'duration', header: 'Duration', sortable: false, format: (_, row) => this.durationLabel(row) },
    { field: 'snapshot_timestamp', header: 'Snapshot', cellType: 'date', sortable: false },
    { field: 'records_fetched', header: 'Records', format: (v) => v ?? '-' },
    {
      field: 'error_message', header: 'Error', sortable: false,
      format: (v) => v ?? '-',
      cellClass: (row) => row.error_message ? 'text-negative' : '',
    },
  ];

  fetchPage = computed<AppFetchFn<FeedRunListItem> | null>(() => {
    this.feedService.selectedFeed();
    const feedId = this.feedId();
    if (!feedId) return null;
    const filter = this.filter();
    return (page, pageSize, sort) => {
      const f = Object.keys(filter).length > 0 ? filter : undefined;
      return this.feedService.loadFeedRuns(feedId, page, pageSize, f, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  navigateToRun = computed(() => {
    const feedId = this.feedId();
    return (row: FeedRunListItem) => ['/feeds', feedId, 'runs', row.id];
  });

  onFilterChange(filter: RunFilter): void {
    this.filter.set(filter);
  }

  private durationLabel(run: FeedRunListItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
