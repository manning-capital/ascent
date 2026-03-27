import { Component, Input } from '@angular/core';
import { DatePipe } from '@angular/common';

export interface RunDetailItem {
  id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  [key: string]: any;
}

export interface RunDetailField {
  label: string;
  key: string;
}

@Component({
  selector: 'app-run-detail-card',
  standalone: true,
  imports: [DatePipe],
  template: `
    <div class="space-y-3">
      <!-- Header: status left, id right -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full" [class]="statusDotClass(run.status)"></span>
          <span class="text-sm font-semibold" [class]="statusClass(run.status)">{{ run.status }}</span>
        </div>
        <span class="text-xs text-fg-faint">#{{ run.id }}</span>
      </div>

      <!-- Detail rows -->
      <div class="rounded-xl border border-edge bg-surface/50 p-4 space-y-3 text-sm">
        <div class="flex justify-between">
          <span class="text-fg-muted">Started</span>
          <span>{{ run.started_at | date:'medium' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-fg-muted">Completed</span>
          <span>{{ run.completed_at ? (run.completed_at | date:'medium') : '-' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-fg-muted">Duration</span>
          <span>{{ durationLabel() }}</span>
        </div>
        @for (field of extraFields; track field.key) {
          <div class="flex justify-between">
            <span class="text-fg-muted">{{ field.label }}</span>
            <span>{{ run[field.key] ?? '-' }}</span>
          </div>
        }
      </div>

      <!-- Error -->
      @if (run.error_message) {
        <div class="rounded-xl border border-negative/30 bg-negative/5 p-4">
          <h4 class="text-xs font-semibold text-negative mb-2">Error</h4>
          <p class="text-xs text-negative/80 whitespace-pre-wrap break-words font-mono">{{ run.error_message }}</p>
        </div>
      }
    </div>
  `,
})
export class RunDetailCardComponent {
  @Input({ required: true }) run!: RunDetailItem;
  @Input() extraFields: RunDetailField[] = [];

  statusClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'text-positive';
      case 'FAILED': return 'text-negative';
      case 'RUNNING': return 'text-warning';
      case 'PENDING': return 'text-fg-muted';
      default: return '';
    }
  }

  statusDotClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'bg-positive';
      case 'FAILED': return 'bg-negative';
      case 'RUNNING': return 'bg-warning animate-pulse';
      case 'PENDING': return 'bg-fg-faint';
      default: return 'bg-fg-faint';
    }
  }

  durationLabel(): string {
    if (!this.run.completed_at) return this.run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(this.run.completed_at).getTime() - new Date(this.run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
