import { Component, computed, input } from '@angular/core';

interface Tick {
  status: string;
  bg: string;
  height: number;
}

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'var(--positive)',
  SUCCEEDED: 'var(--positive)',
  FAILED: 'var(--negative)',
  ERROR: 'var(--negative)',
  RUNNING: 'var(--info)',
  PENDING: 'var(--warning)',
  QUEUED: 'var(--warning)',
  CANCELLED: 'var(--fg-faint)',
};

/**
 * Run-history sparkline: a row of small colored vertical bars, one per
 * recent run. Oldest on the left, newest on the right. Inspired by
 * Prefect / Dagster run timelines.
 *
 *   <app-run-history [statuses]="['COMPLETED','COMPLETED','FAILED','RUNNING']" />
 */
@Component({
  selector: 'app-run-history',
  standalone: true,
  template: `
    @if (ticks().length > 0) {
      <span class="inline-flex items-end gap-px" [style.height.px]="height()">
        @for (t of ticks(); track $index) {
          <span
            class="block rounded-sm shrink-0"
            [style.width.px]="width()"
            [style.height.px]="t.height"
            [style.background]="t.bg"
            [class.animate-pulse-live]="t.status === 'RUNNING'"
            [title]="t.status"
          ></span>
        }
      </span>
    } @else {
      <span class="text-fg-faint text-xs">No runs</span>
    }
  `,
})
export class AppRunHistoryComponent {
  statuses = input<string[]>([]);
  width = input<number>(3);
  height = input<number>(16);

  ticks = computed<Tick[]>(() => {
    const h = this.height();
    return this.statuses().map((s) => {
      const upper = s.toUpperCase();
      return {
        status: upper,
        bg: STATUS_COLORS[upper] ?? 'var(--fg-faint)',
        // Slightly shorter bars for non-terminal states so the timeline
        // still reads cleanly when most runs succeed.
        height: upper === 'COMPLETED' || upper === 'SUCCEEDED' ? h : Math.round(h * 0.85),
      };
    });
  });
}
