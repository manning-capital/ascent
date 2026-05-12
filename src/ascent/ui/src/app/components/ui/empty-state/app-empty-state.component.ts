import { Component, input } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <div class="w-9 h-9 rounded-full bg-edge-dim flex items-center justify-center">
        <i [class]="'pi ' + icon() + ' text-fg-faint'" style="font-size: 1rem;"></i>
      </div>
      <div>
        <p class="text-sm font-medium text-fg-muted">{{ title() }}</p>
        @if (message()) {
          <p class="text-xs text-fg-faint mt-1">{{ message() }}</p>
        }
      </div>
    </div>
  `,
})
export class AppEmptyStateComponent {
  title = input<string>('No data');
  message = input<string>('');
  icon = input<string>('pi-inbox');
}
