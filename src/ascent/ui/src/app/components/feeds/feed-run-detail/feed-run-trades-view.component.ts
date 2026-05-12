import { Component, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem, FeedRunTradeItem } from '../../../models/feed.model';
import { AppEmptyStateComponent } from '../../ui/empty-state/app-empty-state.component';

type Severity = 'success' | 'danger' | 'warn' | 'secondary' | 'info';

@Component({
  selector: 'app-feed-run-trades-view',
  standalone: true,
  imports: [RouterLink, Tag, Skeleton, AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  `],
  template: `
    <div class="flex-1 overflow-y-auto">
      @if (loading()) {
        <div class="p-4 space-y-2">
          <p-skeleton width="100%" height="2rem"/>
          <p-skeleton width="100%" height="2rem"/>
          <p-skeleton width="100%" height="2rem"/>
        </div>
      } @else if (trades().length === 0) {
        <app-empty-state
          title="No trades caused by this run"
          message="No strategy evaluation triggered by this feed event led to a trade."
          icon="inbox"/>
      } @else {
        <table class="w-full text-sm">
          <thead class="sticky top-0 bg-emphasis z-10">
            <tr class="border-b border-surface text-left">
              <th class="py-2 px-3">Trade</th>
              <th class="py-2 px-3">Strategy</th>
              <th class="py-2 px-3">Status</th>
              <th class="py-2 px-3">Entry</th>
              <th class="py-2 px-3">Created</th>
            </tr>
          </thead>
          <tbody>
            @for (t of trades(); track t.trade_id) {
              <tr class="border-b border-surface hover:bg-emphasis">
                <td class="py-2 px-3">
                  <a [routerLink]="['/trades', t.trade_id]" class="text-primary hover:underline font-mono text-xs">
                    {{ t.trade_id.slice(0, 8) }}
                  </a>
                </td>
                <td class="py-2 px-3">
                  <a [routerLink]="['/strategies', t.strategy_id]" class="text-primary hover:underline font-mono text-xs">
                    {{ t.strategy_id.slice(0, 8) }}
                  </a>
                </td>
                <td class="py-2 px-3">
                  <p-tag [value]="t.status" [severity]="statusSeverity(t.status)" [rounded]="true"/>
                </td>
                <td class="py-2 px-3">{{ t.entry_at || '—' }}</td>
                <td class="py-2 px-3">{{ t.created_at }}</td>
              </tr>
            }
          </tbody>
        </table>
      }
    </div>
  `,
})
export class FeedRunTradesViewComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();
  run = input<FeedRunListItem | null>(null);

  trades = signal<FeedRunTradeItem[]>([]);
  loading = signal(false);

  constructor() {
    effect(() => {
      const r = this.run();
      const fid = this.feedId();
      if (!r || !fid) return;
      this.loadTrades(fid, r.id);
    });
  }

  private loadTrades(feedId: string, runId: string): void {
    this.loading.set(true);
    this.feedService.loadRunTrades(feedId, runId).subscribe({
      next: trades => {
        this.trades.set(trades);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  statusSeverity(status: string): Severity {
    switch (status) {
      case 'COMPLETED':
      case 'OPEN':
      case 'CLOSED': return 'success';
      case 'FAILED':
      case 'ERROR': return 'danger';
      case 'RUNNING':
      case 'OPENING':
      case 'CLOSING': return 'warn';
      case 'PENDING':
      case 'WAITING': return 'secondary';
      default: return 'secondary';
    }
  }
}
