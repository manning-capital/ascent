import { Component, computed, input } from '@angular/core';
import { AppSeverity } from '../data-table/app-column.model';

/**
 * Compact colored dot for inline status indicators.
 * Use to put a status hint at the start of a name cell so the right
 * column doesn't have to carry the status tag.
 */
@Component({
  selector: 'app-status-dot',
  standalone: true,
  template: `
    <span
      class="inline-block rounded-full shrink-0"
      [style.width.px]="size()"
      [style.height.px]="size()"
      [style.background]="bg()"
      [class.animate-pulse-live]="pulse()"
    ></span>
  `,
})
export class AppStatusDotComponent {
  severity = input<AppSeverity>('secondary');
  size = input<number>(8);
  pulse = input<boolean>(false);

  bg = computed(() => {
    switch (this.severity()) {
      case 'success': return 'var(--positive)';
      case 'danger': return 'var(--negative)';
      case 'warn': return 'var(--warning)';
      case 'info': return 'var(--info)';
      case 'contrast': return 'var(--fg)';
      default: return 'var(--fg-faint)';
    }
  });
}
