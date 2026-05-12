import { Component, input } from '@angular/core';
import { AppSeverity } from '../data-table/app-column.model';
import { AppStatusDotComponent } from './app-status-dot.component';

/**
 * Two-line name cell: bold display name (with optional status dot) +
 * subtitle line for code / handle / secondary identifier.
 */
@Component({
  selector: 'app-named-cell',
  standalone: true,
  imports: [AppStatusDotComponent],
  template: `
    <div class="flex flex-col gap-0.5 min-w-0">
      <div class="flex items-center gap-2 min-w-0">
        @if (showDot()) {
          <app-status-dot [severity]="dotSeverity()" [pulse]="pulse()" />
        }
        <span class="text-sm font-semibold text-fg truncate">{{ name() }}</span>
      </div>
      @if (subtitle()) {
        <span class="text-[11px] font-mono text-fg-faint truncate" [class.pl-4]="showDot()">
          {{ subtitle() }}
        </span>
      }
    </div>
  `,
})
export class AppNamedCellComponent {
  name = input.required<string>();
  subtitle = input<string | null | undefined>(undefined);
  showDot = input<boolean>(false);
  dotSeverity = input<AppSeverity>('secondary');
  pulse = input<boolean>(false);
}
