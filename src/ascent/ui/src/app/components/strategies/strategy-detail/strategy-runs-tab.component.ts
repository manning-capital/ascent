import { Component, computed, inject, input, signal } from '@angular/core';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { StrategyService } from '../../../services/strategy.service';
import { StrategyRunListItem } from '../../../models/feed.model';
import { DataTableColumn, ServerFetchFn } from '../../shared/data-table/data-table.model';
import { ServerTableComponent } from '../../shared/data-table/server-table.component';
import { RunFilterPanelComponent } from '../../shared/run-filter-panel.component';
import type { RunFilter } from '../../shared/run-viewer.component';

@Component({
  selector: 'app-strategy-runs-tab',
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
export class StrategyRunsTabComponent {
  private feedService = inject(FeedService);
  private strategyService = inject(StrategyService);

  strategyId = input.required<string>();

  private filter = signal<RunFilter>({});

  runColumns: DataTableColumn<StrategyRunListItem>[] = [
    { field: 'status', header: 'Status', cellType: 'tag', width: 96, tagMapper: (v: string) => {
      const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
    { field: 'id', header: 'Run ID', cellType: 'monospace', sortable: false },
    { field: 'started_at', header: 'Started', cellType: 'date' },
    { field: 'duration', header: 'Duration', sortable: false, valueGetter: (p: any) => this.durationLabel(p.data) },
    { field: 'feed_runs', header: 'Feeds', sortable: false, valueGetter: (p: any) => p.data?.feed_runs?.length ?? 0 },
    { field: 'error_message', header: 'Error', sortable: false, valueFormatter: (p: any) => p.value ?? '-', cellClass: (p: any) => p.value ? 'text-red-500' : '' },
  ];

  fetchPage = computed<ServerFetchFn<StrategyRunListItem> | null>(() => {
    this.strategyService.selectedStrategy(); // track strategy changes
    const id = this.strategyId();
    if (!id) return null;
    const filter = this.filter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const f = Object.keys(filter).length > 0 ? filter : undefined;
      return this.feedService.loadStrategyRuns(id, page, pageSize, f, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  navigateToRun = computed(() => {
    const id = this.strategyId();
    return (row: StrategyRunListItem) => ['/strategies', id, 'runs', row.id];
  });

  onFilterChange(filter: RunFilter): void {
    this.filter.set(filter);
  }

  private durationLabel(run: StrategyRunListItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
