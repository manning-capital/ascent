import { Component, computed, input } from '@angular/core';
import { FeedRunContext, FeedRunDetail } from '../../../models/feed.model';
import { AppEmptyStateComponent } from '../../ui/empty-state/app-empty-state.component';

@Component({
  selector: 'app-feed-run-context-view',
  standalone: true,
  imports: [AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  `],
  template: `
    @if (parsed(); as ctx) {
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        @if (ctx.snapshot_timestamp) {
          <div class="flex items-baseline gap-2 text-sm">
            <span class="text-surface-500">Snapshot timestamp:</span>
            <span class="font-mono">{{ ctx.snapshot_timestamp }}</span>
          </div>
        }
        @for (source of ctx.sources; track $index) {
          <div class="border border-edge rounded-lg overflow-hidden">
            <div class="bg-emphasis px-3 py-2 border-b border-edge flex items-center gap-3">
              <span class="text-xs font-semibold uppercase text-surface-500">{{ source.scope_type }}</span>
              <span class="font-mono text-sm">{{ source.table }}</span>
              <span class="ml-auto text-xs text-surface-500">{{ source.attributes.length }} attribute{{ source.attributes.length === 1 ? '' : 's' }}</span>
            </div>
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-edge text-left text-xs text-surface-500">
                  <th class="px-3 py-2 font-medium">Display Name</th>
                  <th class="px-3 py-2 font-medium">Name</th>
                  <th class="px-3 py-2 font-medium">Period</th>
                </tr>
              </thead>
              <tbody>
                @for (attr of source.attributes; track attr.id) {
                  <tr class="border-b border-edge last:border-b-0">
                    <td class="px-3 py-2">{{ attr.display_name || attr.name }}</td>
                    <td class="px-3 py-2 font-mono text-xs">{{ attr.name }}</td>
                    <td class="px-3 py-2 text-surface-500">{{ attr.period?.name || '—' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>
    } @else {
      <app-empty-state
        title="No context recorded for this run"
        message="This run did not persist a context snapshot."
        icon="inbox"/>
    }
  `,
})
export class FeedRunContextViewComponent {
  run = input<FeedRunDetail | null>(null);

  parsed = computed<FeedRunContext | null>(() => {
    const ctx = this.run()?.context;
    if (!ctx || !ctx.sources || ctx.sources.length === 0) return null;
    return ctx;
  });
}
