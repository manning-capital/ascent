import { Component, computed, inject, input } from '@angular/core';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import type { AppColumn, AppFetchFn } from '../../ui/data-table/app-column.model';

@Component({
  selector: 'app-feed-run-universe-view',
  standalone: true,
  imports: [AppDataTableComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  `],
  template: `
    <div class="flex flex-col h-full min-h-0">
      <div class="px-4 py-2 text-xs font-semibold text-fg-muted shrink-0 border-b border-edge">Instruments</div>
      <app-data-table class="flex-1 min-h-0"
        [columns]="instrumentColumns"
        [fetchPage]="instrumentsFetch()"
        [edgeToEdge]="true"
        emptyMessage="No instruments in universe at this snapshot."/>
      <div class="px-4 py-2 text-xs font-semibold text-fg-muted shrink-0 border-y border-edge">Composites</div>
      <app-data-table class="flex-1 min-h-0"
        [columns]="compositeColumns"
        [fetchPage]="compositesFetch()"
        [edgeToEdge]="true"
        emptyMessage="No composites in universe at this snapshot."/>
    </div>
  `,
})
export class FeedRunUniverseViewComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();
  run = input<FeedRunListItem | null>(null);

  instrumentColumns: AppColumn<any>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'instrument_type_name', header: 'Type' },
    { field: 'added_at', header: 'Added At', cellType: 'date' },
  ];

  compositeColumns: AppColumn<any>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'composite_type_name', header: 'Type' },
    { field: 'added_at', header: 'Added At', cellType: 'date' },
  ];

  instrumentsFetch = computed<AppFetchFn<any> | null>(() => {
    const r = this.run();
    if (!r) return null;
    const feedId = this.feedId();
    const runId = r.id;
    return (page, pageSize) =>
      this.feedService.loadFeedRunUniverseInstruments(feedId, runId, page, pageSize).pipe(
        map(res => ({ items: res.items, total: res.total })),
      );
  });

  compositesFetch = computed<AppFetchFn<any> | null>(() => {
    const r = this.run();
    if (!r) return null;
    const feedId = this.feedId();
    const runId = r.id;
    return (page, pageSize) =>
      this.feedService.loadFeedRunUniverseComposites(feedId, runId, page, pageSize).pipe(
        map(res => ({ items: res.items, total: res.total })),
      );
  });
}
