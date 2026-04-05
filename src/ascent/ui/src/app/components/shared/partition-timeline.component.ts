import { Component, input, output } from '@angular/core';
import { Tooltip } from 'primeng/tooltip';

export interface PartitionCell {
  partition_key: string;
  status: string;
  id: string | null;
  window_start: string;
  window_end: string;
  run_id?: string;
}

@Component({
  selector: 'app-partition-timeline',
  standalone: true,
  imports: [Tooltip],
  template: `
    <div class="space-y-3">
      <!-- Legend -->
      <div class="flex items-center gap-4 text-xs text-muted-color">
        <div class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-green-500"></span>
          <span>Materialized</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-red-500"></span>
          <span>Failed</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-surface-600"></span>
          <span>Pending</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm border border-surface-500 bg-transparent"></span>
          <span>Missing</span>
        </div>
        <div class="ml-auto text-muted-color">
          {{ partitions().length }} partitions
        </div>
      </div>

      <!-- Timeline grid -->
      <div class="flex flex-wrap gap-[3px]">
        @for (p of partitions(); track p.partition_key) {
          <div
            class="w-4 h-4 rounded-sm cursor-pointer transition-transform hover:scale-125 hover:z-10"
            [class]="cellClass(p.status)"
            [pTooltip]="tooltipFor(p)"
            tooltipPosition="top"
            (click)="cellClick.emit(p)"
          ></div>
        }
      </div>
    </div>
  `,
})
export class PartitionTimelineComponent {
  partitions = input.required<PartitionCell[]>();
  cellClick = output<PartitionCell>();

  cellClass(status: string): string {
    switch (status) {
      case 'MATERIALIZED': return 'bg-green-500';
      case 'FAILED': return 'bg-red-500';
      case 'PENDING': return 'bg-surface-600';
      default: return 'border border-surface-500 bg-transparent';
    }
  }

  tooltipFor(p: PartitionCell): string {
    const date = new Date(p.partition_key);
    const formatted = date.toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
    return `${formatted}\n${p.status}`;
  }
}
