import { Component, input, model } from '@angular/core';

@Component({
  selector: 'app-panel-tabs',
  standalone: true,
  template: `
    <div class="flex border-b border-edge">
      @for (tab of tabs(); track tab) {
        <button
          (click)="activeTab.set(tab)"
          class="px-4 py-2 text-sm transition-colors relative"
          [class]="activeTab() === tab
            ? 'text-fg'
            : 'text-fg-muted hover:text-fg'">
          {{ tab }}
          @if (activeTab() === tab) {
            <span class="absolute bottom-0 left-0 right-0 h-0.5 bg-info"></span>
          }
        </button>
      }
    </div>
  `,
})
export class PanelTabsComponent {
  tabs = input.required<string[]>();
  activeTab = model<string>('');
}
