import { Component, computed, effect, inject, input, model, signal } from '@angular/core';
import { Panel } from 'primeng/panel';
import { FeedService } from '../../../services/feed.service';
import { FeedRunDetail, FeedRunLineageResponse } from '../../../models/feed.model';

@Component({
  selector: 'app-feed-run-stats-rail',
  standalone: true,
  imports: [Panel],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; height: 100%; }
    :host ::ng-deep .p-panel-header { padding: 0.5rem 0.75rem; }
    :host ::ng-deep .p-panel-content { padding: 0.5rem 0.75rem; }
  `],
  template: `
    <div class="h-full flex flex-col border-l border-edge bg-emphasis">
      @if (collapsed()) {
        <button (click)="collapsed.set(false)"
                class="p-2 text-surface-500 hover:bg-surface flex items-center justify-center"
                aria-label="Expand stats rail"
                title="Expand">
          <i class="pi pi-chevron-left"></i>
        </button>
      } @else {
        <div class="flex items-center justify-between px-3 py-2 border-b border-edge shrink-0">
          <span class="text-xs font-semibold text-surface-500">Run details</span>
          <button (click)="collapsed.set(true)"
                  class="text-surface-500 hover:text-fg p-1"
                  aria-label="Collapse stats rail"
                  title="Collapse">
            <i class="pi pi-chevron-right"></i>
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-2 space-y-2">
          <p-panel header="Lineage" [toggleable]="true">
            @if (loading()) {
              <span class="text-xs text-surface-500">Loading…</span>
            } @else if (lineage(); as l) {
              <div class="text-sm space-y-1">
                <div class="flex justify-between"><span class="text-surface-500">Upstream feed runs</span><span>{{ l.upstream_runs.length }}</span></div>
                <div class="flex justify-between"><span class="text-surface-500">Downstream strategy runs</span><span>{{ l.downstream_strategy_runs.length }}</span></div>
                <div class="flex justify-between"><span class="text-surface-500">Downstream trades</span><span>{{ l.downstream_trades.length }}</span></div>
                @if (tradeStatusBreakdown().length > 0) {
                  <div class="text-xs text-surface-500 mt-1">By status:</div>
                  @for (entry of tradeStatusBreakdown(); track entry.status) {
                    <div class="flex justify-between text-xs"><span>{{ entry.status }}</span><span>{{ entry.count }}</span></div>
                  }
                }
              </div>
            } @else {
              <span class="text-xs text-surface-500">No lineage</span>
            }
          </p-panel>

          <p-panel header="Context" [toggleable]="true">
            @if (run()?.context; as ctx) {
              <div class="text-sm space-y-1">
                <div class="flex justify-between"><span class="text-surface-500">Sources</span><span>{{ ctx.sources.length }}</span></div>
                @for (s of ctx.sources; track $index) {
                  <div class="flex justify-between text-xs">
                    <span class="font-mono truncate" [title]="s.table">{{ s.table }}</span>
                    <span>{{ s.attributes.length }} attr</span>
                  </div>
                }
              </div>
            } @else {
              <span class="text-xs text-surface-500">No context recorded</span>
            }
          </p-panel>

          <p-panel header="Timing" [toggleable]="true">
            @if (run(); as r) {
              <div class="text-sm space-y-1">
                <div class="flex flex-col">
                  <span class="text-surface-500 text-xs">Started</span>
                  <span class="font-mono text-xs break-all">{{ r.started_at }}</span>
                </div>
                <div class="flex flex-col">
                  <span class="text-surface-500 text-xs">Completed</span>
                  <span class="font-mono text-xs break-all">{{ r.completed_at || '—' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-surface-500">Duration</span>
                  <span>{{ duration() }}</span>
                </div>
                <div class="flex flex-col">
                  <span class="text-surface-500 text-xs">Snapshot</span>
                  <span class="font-mono text-xs break-all">{{ r.snapshot_timestamp }}</span>
                </div>
              </div>
            }
          </p-panel>

          <p-panel header="Params" [toggleable]="true">
            @if (paramsKeys().length > 0) {
              <div class="text-sm space-y-1">
                @for (key of paramsKeys(); track key) {
                  <div class="flex justify-between gap-2">
                    <span class="text-surface-500 text-xs truncate">{{ key }}</span>
                    <span class="font-mono text-xs truncate" [title]="formatParamValue(key)">{{ formatParamValue(key) }}</span>
                  </div>
                }
              </div>
            } @else {
              <span class="text-xs text-surface-500">No params for this run</span>
            }
          </p-panel>
        </div>
      }
    </div>
  `,
})
export class FeedRunStatsRailComponent {
  private feedService = inject(FeedService);

  feedId = input.required<string>();
  run = input<FeedRunDetail | null>(null);
  collapsed = model<boolean>(false);

  lineage = signal<FeedRunLineageResponse | null>(null);
  loading = signal(false);

  constructor() {
    effect(() => {
      const r = this.run();
      const fid = this.feedId();
      if (!r || !fid) return;
      this.fetchLineage(fid, r.id);
    });
  }

  tradeStatusBreakdown = computed(() => {
    const trades = this.lineage()?.downstream_trades ?? [];
    const counts = new Map<string, number>();
    for (const t of trades) counts.set(t.status, (counts.get(t.status) ?? 0) + 1);
    return Array.from(counts.entries()).map(([status, count]) => ({ status, count }));
  });

  paramsKeys = computed<string[]>(() => {
    const ctx = this.run()?.context as Record<string, any> | null | undefined;
    const params = (ctx as any)?.params;
    if (params && typeof params === 'object') return Object.keys(params);
    return [];
  });

  duration = computed<string>(() => {
    const r = this.run();
    if (!r) return '—';
    if (!r.completed_at) return r.status === 'RUNNING' ? 'running…' : '—';
    const ms = new Date(r.completed_at).getTime() - new Date(r.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60_000).toFixed(1)}m`;
  });

  formatParamValue(key: string): string {
    const ctx = this.run()?.context as any;
    const v = ctx?.params?.[key];
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }

  private fetchLineage(feedId: string, runId: string): void {
    this.loading.set(true);
    this.feedService.loadFeedRunLineage(feedId, runId).subscribe({
      next: lineage => {
        this.lineage.set(lineage);
        this.loading.set(false);
      },
      error: () => {
        this.lineage.set(null);
        this.loading.set(false);
      },
    });
  }
}
