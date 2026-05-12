import { Component, computed, effect, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { FeedRunDetail } from '../../../models/feed.model';
import { FeedRunDataViewComponent } from './feed-run-data-view.component';
import { FeedRunTradesViewComponent } from './feed-run-trades-view.component';
import { FeedRunUniverseViewComponent } from './feed-run-universe-view.component';
import { FeedRunContextViewComponent } from './feed-run-context-view.component';
import { FeedRunLogsViewComponent } from './feed-run-logs-view.component';

type BottomView = 'data' | 'trades' | 'universe' | 'context' | 'logs';

const STORAGE_KEY = 'feed-run-detail-bottom-view';

@Component({
  selector: 'app-feed-run-bottom-panel',
  standalone: true,
  imports: [
    FormsModule,
    Select,
    FeedRunDataViewComponent,
    FeedRunTradesViewComponent,
    FeedRunUniverseViewComponent,
    FeedRunContextViewComponent,
    FeedRunLogsViewComponent,
  ],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; height: 100%; }
  `],
  template: `
    <div class="flex flex-col h-full min-h-0">
      <div class="flex items-center gap-2 px-4 py-2 border-b border-edge shrink-0 bg-emphasis">
        <span class="text-xs text-surface-500">View:</span>
        <p-select [options]="options" [(ngModel)]="view" optionLabel="label" optionValue="value" appendTo="body" size="small"/>
      </div>
      <div class="flex-1 min-h-0 flex flex-col">
        @switch (view()) {
          @case ('data')     { <app-feed-run-data-view     [run]="run()" [feedId]="feedId()"/> }
          @case ('trades')   { <app-feed-run-trades-view   [run]="run()" [feedId]="feedId()"/> }
          @case ('universe') { <app-feed-run-universe-view [run]="run()" [feedId]="feedId()"/> }
          @case ('context')  { <app-feed-run-context-view  [run]="run()"/> }
          @case ('logs')     { <app-feed-run-logs-view/> }
        }
      </div>
    </div>
  `,
})
export class FeedRunBottomPanelComponent {
  feedId = input.required<string>();
  run = input<FeedRunDetail | null>(null);

  options = [
    { label: 'Data', value: 'data' as BottomView },
    { label: 'Trades', value: 'trades' as BottomView },
    { label: 'Universe', value: 'universe' as BottomView },
    { label: 'Context', value: 'context' as BottomView },
    { label: 'Logs', value: 'logs' as BottomView },
  ];

  view = signal<BottomView>(this.loadInitial());

  constructor() {
    effect(() => {
      try {
        localStorage.setItem(STORAGE_KEY, this.view());
      } catch {
        // localStorage may be unavailable
      }
    });
  }

  private loadInitial(): BottomView {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as BottomView | null;
      const valid = ['data', 'trades', 'universe', 'context', 'logs'];
      if (stored && valid.includes(stored)) return stored;
    } catch {
      // ignore
    }
    return 'data';
  }
}
