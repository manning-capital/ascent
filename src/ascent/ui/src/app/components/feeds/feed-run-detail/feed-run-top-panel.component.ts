import { Component, effect, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { FeedRunDetail } from '../../../models/feed.model';
import { FeedRunLineageTimelineComponent } from './feed-run-lineage-timeline.component';
import { FeedRunLineageDagComponent } from './feed-run-lineage-dag.component';

type TopView = 'timeline' | 'dag';

const STORAGE_KEY = 'feed-run-detail-top-view';

@Component({
  selector: 'app-feed-run-top-panel',
  standalone: true,
  imports: [
    FormsModule,
    Select,
    FeedRunLineageTimelineComponent,
    FeedRunLineageDagComponent,
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
          @case ('timeline') { <app-feed-run-lineage-timeline [run]="run()" [feedId]="feedId()"/> }
          @case ('dag')      { <app-feed-run-lineage-dag      [run]="run()" [feedId]="feedId()"/> }
        }
      </div>
    </div>
  `,
})
export class FeedRunTopPanelComponent {
  feedId = input.required<string>();
  run = input<FeedRunDetail | null>(null);

  options = [
    { label: 'Lineage timeline', value: 'timeline' as TopView },
    { label: 'Lineage DAG', value: 'dag' as TopView },
  ];

  view = signal<TopView>(this.loadInitial());

  constructor() {
    effect(() => {
      try {
        localStorage.setItem(STORAGE_KEY, this.view());
      } catch {
        // ignore
      }
    });
  }

  private loadInitial(): TopView {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as TopView | null;
      if (stored === 'timeline' || stored === 'dag') return stored;
    } catch {
      // ignore
    }
    return 'timeline';
  }
}
