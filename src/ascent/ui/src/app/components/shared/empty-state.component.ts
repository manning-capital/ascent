import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <div class="w-11 h-11 rounded-full bg-emphasis flex items-center justify-center">
        @switch (icon) {
          @case ('inbox') {
            <!-- Inbox icon -->
            <svg class="w-5 h-5 text-fg-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>
              <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
            </svg>
          }
          @case ('select') {
            <!-- Mouse pointer / click icon -->
            <svg class="w-5 h-5 text-fg-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="m4 4 7.07 17 2.51-7.39L21 11.07z"/>
            </svg>
          }
          @case ('search') {
            <!-- Search icon -->
            <svg class="w-5 h-5 text-fg-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.3-4.3"/>
            </svg>
          }
          @default {
            <!-- Table/data icon -->
            <svg class="w-5 h-5 text-fg-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v18"/>
              <rect width="18" height="18" x="3" y="3" rx="2"/>
              <path d="M3 9h18"/>
              <path d="M3 15h18"/>
            </svg>
          }
        }
      </div>
      <div>
        <p class="text-sm font-medium text-fg-muted">{{ title }}</p>
        @if (message) {
          <p class="text-xs text-fg-faint mt-1">{{ message }}</p>
        }
      </div>
    </div>
  `,
})
export class EmptyStateComponent {
  @Input() title = 'No data';
  @Input() message = '';
  @Input() icon: 'data' | 'inbox' | 'select' | 'search' = 'data';
}
