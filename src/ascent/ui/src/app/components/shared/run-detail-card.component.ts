import { Component, Input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { Message } from 'primeng/message';

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
  imports: [DatePipe, Card, Tag, Message],
  template: `
    <p-card>
      <ng-template #header>
        <div class="flex items-center justify-between p-4 pb-0">
          <p-tag [value]="run.status" [severity]="statusSeverity(run.status)" [rounded]="true"/>
          <span class="text-sm text-surface-500">#{{ run.id }}</span>
        </div>
      </ng-template>

      <div class="flex flex-col gap-3 text-sm">
        <div class="flex justify-between">
          <span class="text-surface-500">Started</span>
          <span>{{ run.started_at | date:'medium' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-surface-500">Completed</span>
          <span>{{ run.completed_at ? (run.completed_at | date:'medium') : '-' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-surface-500">Duration</span>
          <span>{{ durationLabel() }}</span>
        </div>
        @for (field of extraFields; track field.key) {
          <div class="flex justify-between">
            <span class="text-surface-500">{{ field.label }}</span>
            <span>{{ run[field.key] ?? '-' }}</span>
          </div>
        }
      </div>

      @if (run.error_message) {
        <p-message severity="error" class="mt-3 block">
          <span class="text-xs font-mono whitespace-pre-wrap break-words">{{ run.error_message }}</span>
        </p-message>
      }
    </p-card>
  `,
})
export class RunDetailCardComponent {
  @Input({ required: true }) run!: RunDetailItem;
  @Input() extraFields: RunDetailField[] = [];

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'info';
    }
  }

  durationLabel(): string {
    if (!this.run.completed_at) return this.run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(this.run.completed_at).getTime() - new Date(this.run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
