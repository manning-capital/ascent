import { Component, computed, input } from '@angular/core';
import { AppSeverity } from '../data-table/app-column.model';

/**
 * Inline horizontal progress bar for percentage/rate columns.
 * Default width 64px works well in compact tables.
 */
@Component({
  selector: 'app-progress-bar',
  standalone: true,
  template: `
    <span class="inline-flex items-center gap-2">
      <span class="tabular-nums text-xs text-fg" [class.shrink-0]="true">{{ label() }}</span>
      <span
        class="inline-block rounded-sm overflow-hidden shrink-0"
        [style.width.px]="width()"
        [style.height.px]="6"
        style="background: var(--edge-dim);"
      >
        <span
          class="block h-full"
          [style.width.%]="clamped()"
          [style.background]="bg()"
        ></span>
      </span>
    </span>
  `,
})
export class AppProgressBarComponent {
  value = input.required<number | null | undefined>();
  max = input<number>(100);
  width = input<number>(64);
  severity = input<AppSeverity>('info');
  format = input<((v: number) => string) | undefined>(undefined);

  clamped = computed(() => {
    const v = this.value();
    if (v == null) return 0;
    const m = this.max();
    if (m <= 0) return 0;
    return Math.max(0, Math.min(100, (v / m) * 100));
  });

  label = computed(() => {
    const v = this.value();
    if (v == null) return '—';
    const fmt = this.format();
    if (fmt) return fmt(v);
    return `${Math.round(v)}%`;
  });

  bg = computed(() => {
    switch (this.severity()) {
      case 'success': return 'var(--positive)';
      case 'danger': return 'var(--negative)';
      case 'warn': return 'var(--warning)';
      case 'info': return 'var(--info)';
      default: return 'var(--fg-faint)';
    }
  });
}
