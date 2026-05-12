import { Component, input, output } from '@angular/core';
import { Button } from 'primeng/button';

@Component({
  selector: 'app-danger-zone',
  standalone: true,
  imports: [Button],
  template: `
    <section class="rounded-md border border-negative/40 bg-negative/5 p-4">
      <h3 class="text-sm font-semibold text-negative mb-1">{{ title() }}</h3>
      <p class="text-xs text-fg-muted mb-3">{{ description() }}</p>
      <p-button
        [label]="actionLabel()"
        [icon]="icon()"
        severity="danger"
        size="small"
        [outlined]="true"
        [loading]="loading()"
        [disabled]="disabled()"
        (onClick)="confirmed.emit()" />
    </section>
  `,
})
export class AppDangerZoneComponent {
  title = input.required<string>();
  description = input.required<string>();
  actionLabel = input.required<string>();
  icon = input<string>('pi pi-trash');
  loading = input(false);
  disabled = input(false);

  readonly confirmed = output<void>();
}
