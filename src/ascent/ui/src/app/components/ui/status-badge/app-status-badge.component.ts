import { Component, computed, input } from '@angular/core';
import { Tag } from 'primeng/tag';

export type AppStatusSeverity =
  | 'success'
  | 'info'
  | 'warn'
  | 'danger'
  | 'secondary'
  | 'contrast';

export type AppStatusMapping = (value: string) => AppStatusSeverity;

const DEFAULT_MAPPING: Record<string, AppStatusSeverity> = {
  RUNNING: 'info',
  PENDING: 'secondary',
  QUEUED: 'secondary',
  COMPLETED: 'success',
  SUCCESS: 'success',
  SUCCEEDED: 'success',
  FILLED: 'success',
  ACTIVE: 'success',
  LIVE: 'success',
  OPEN: 'info',
  CLOSED: 'secondary',
  FAILED: 'danger',
  ERROR: 'danger',
  REJECTED: 'danger',
  CANCELLED: 'warn',
  CANCELED: 'warn',
  PAUSED: 'warn',
  PARTIAL: 'warn',
  PARTIAL_FILL: 'warn',
};

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [Tag],
  template: `<p-tag [value]="label()" [severity]="severity()" [rounded]="rounded()" />`,
})
export class AppStatusBadgeComponent {
  value = input.required<string | null | undefined>();
  mapping = input<AppStatusMapping | undefined>(undefined);
  rounded = input(false);

  label = computed(() => {
    const v = this.value();
    return v == null ? '—' : String(v);
  });

  severity = computed<AppStatusSeverity>(() => {
    const v = this.value();
    if (v == null) return 'secondary';
    const upper = String(v).toUpperCase();
    const custom = this.mapping();
    if (custom) return custom(String(v));
    return DEFAULT_MAPPING[upper] ?? 'secondary';
  });
}
