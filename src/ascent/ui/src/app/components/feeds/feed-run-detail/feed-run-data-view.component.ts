import { Component, computed, inject, input } from '@angular/core';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import { AppEmptyStateComponent } from '../../ui/empty-state/app-empty-state.component';
import type { AppFetchFn } from '../../ui/data-table/app-column.model';

@Component({
  selector: 'app-feed-run-data-view',
  standalone: true,
  imports: [AppDataTableComponent, AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  `],
  template: `
    @if (run()) {
      <app-data-table class="flex-1 min-h-0"
        [fetchPage]="fetchPage()"
        [autoColumns]="true"
        [autoLinks]="true"
        [gridLines]="true"
        [edgeToEdge]="true" />
    } @else {
      <app-empty-state title="Run not loaded" message="Waiting for run details." icon="inbox"/>
    }
  `,
})
export class FeedRunDataViewComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();
  run = input<FeedRunListItem | null>(null);

  fetchPage = computed<AppFetchFn<Record<string, any>> | null>(() => {
    const r = this.run();
    if (!r) return null;
    const feedId = this.feedId();
    const runId = r.id;
    return (page, pageSize) =>
      this.feedService.loadRunData(feedId, runId, page, pageSize).pipe(
        map(res => ({ items: res.items, total: res.total })),
      );
  });
}
