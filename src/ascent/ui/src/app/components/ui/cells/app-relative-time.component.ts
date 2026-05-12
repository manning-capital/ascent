import { Component, computed, input } from '@angular/core';

/**
 * Renders an ISO timestamp as a relative phrase ("2m ago", "3h ago").
 * Falls back to em-dash when value is null.
 */
@Component({
  selector: 'app-relative-time',
  standalone: true,
  template: `<span class="text-xs text-fg-muted tabular-nums" [title]="absoluteLabel()">{{ relativeLabel() }}</span>`,
})
export class AppRelativeTimeComponent {
  value = input<string | Date | null | undefined>(null);

  relativeLabel = computed(() => {
    const v = this.value();
    if (!v) return '—';
    const date = typeof v === 'string' ? new Date(v) : v;
    const ms = Date.now() - date.getTime();
    if (Number.isNaN(ms)) return '—';
    const sec = Math.round(ms / 1000);
    if (sec < 5) return 'just now';
    if (sec < 60) return `${sec}s ago`;
    const min = Math.round(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.round(hr / 24);
    if (day < 30) return `${day}d ago`;
    const mo = Math.round(day / 30);
    if (mo < 12) return `${mo}mo ago`;
    const yr = Math.round(mo / 12);
    return `${yr}y ago`;
  });

  absoluteLabel = computed(() => {
    const v = this.value();
    if (!v) return '';
    const date = typeof v === 'string' ? new Date(v) : v;
    return date.toLocaleString();
  });
}
