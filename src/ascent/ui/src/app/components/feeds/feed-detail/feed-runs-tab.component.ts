import { Component, computed, inject, input, signal } from '@angular/core';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { DataTableColumn, ServerFetchFn } from '../../shared/data-table/data-table.model';
import { ServerTableComponent } from '../../shared/data-table/server-table.component';
import { RunFilterPanelComponent } from '../../shared/run-filter-panel.component';
import type { RunFilter } from '../../shared/run-viewer.component';

@Component({
  selector: 'app-feed-runs-tab',
  standalone: true,
  imports: [ServerTableComponent, RunFilterPanelComponent],
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

      <app-server-table class="flex-1 min-h-0"
        [columns]="runColumns"
        [fetchPage]="fetchPage()"
        [rowClickRoute]="navigateToRun()"
        [pageSize]="25"
        emptyMessage="No runs yet."/>
    </div>
  `,
})
export class FeedRunsTabComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();

  private filter = signal<RunFilter>({});

  runColumns: DataTableColumn<FeedRunListItem>[] = [
    { field: 'status', header: 'Status', cellType: 'tag', width: 96, tagMapper: (v: string) => {
      const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
    { field: 'id', header: 'Run ID', cellType: 'monospace' },
    { field: 'started_at', header: 'Started', cellType: 'date' },
    { field: 'duration', header: 'Duration', valueGetter: (p: any) => this.durationLabel(p.data) },
    { field: 'partition_key', header: 'Partition Key', cellType: 'date' },
    { field: 'records_fetched', header: 'Records', valueFormatter: (p: any) => p.value ?? '-' },
    { field: 'error_message', header: 'Error', valueFormatter: (p: any) => p.value ?? '-', cellClass: (p: any) => p.value ? 'text-red-500' : '' },
  ];

  fetchPage = computed<ServerFetchFn<FeedRunListItem> | null>(() => {
    this.feedService.selectedFeed(); // track feed changes
    const feedId = this.feedId();
    if (!feedId) return null;
    const filter = this.filter();
    return (page: number, pageSize: number) => {
      const f = Object.keys(filter).length > 0 ? filter : undefined;
      return this.feedService.loadFeedRuns(feedId, page, pageSize, f).pipe(
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
