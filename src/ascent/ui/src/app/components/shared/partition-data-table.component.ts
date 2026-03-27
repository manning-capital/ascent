import { Component, Input, Output, EventEmitter, computed } from '@angular/core';

@Component({
  selector: 'app-partition-data-table',
  standalone: true,
  styles: [`
    :host { display: flex; flex-direction: column; min-height: 0; }
  `],
  template: `
    @if (loading) {
      <div class="flex items-center justify-center flex-1 text-sm text-fg-faint">Loading data...</div>
    } @else if (data.length === 0) {
      <div class="flex items-center justify-center flex-1 text-sm text-fg-faint">No data for this partition.</div>
    } @else {
      <!-- Header with stats -->
      <div class="px-3 py-2 border-b border-edge shrink-0 flex items-center justify-between">
        <span class="text-[11px] text-fg-faint">{{ total }} total rows</span>
        <span class="text-[11px] text-fg-faint">Page {{ page }} / {{ totalPages || 1 }}</span>
      </div>

      <!-- Table body — scrollable with hidden scrollbar -->
      <div class="flex-1 min-h-0 overflow-y-auto">
        <table class="w-full text-[11px]">
          <thead class="sticky top-0 bg-surface z-10">
            <tr>
              @for (col of columns(); track col) {
                <th class="text-left px-2 py-1.5 text-fg-muted font-medium border-b border-edge whitespace-nowrap">{{ col }}</th>
              }
            </tr>
          </thead>
          <tbody>
            @for (row of data; track $index) {
              <tr class="border-b border-edge-dim hover:bg-fg/[.03] transition-colors">
                @for (col of columns(); track col) {
                  <td class="px-2 py-1.5 text-fg whitespace-nowrap font-mono">{{ row[col] ?? '-' }}</td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>

      <!-- Pagination footer -->
      <div class="flex items-center justify-end px-3 py-2 border-t border-edge shrink-0 gap-1.5">
        <button
          [disabled]="page <= 1"
          (click)="pageChange.emit(page - 1)"
          class="px-2 py-0.5 rounded text-[11px] border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors text-fg-muted">
          Prev
        </button>
        <button
          [disabled]="page >= totalPages"
          (click)="pageChange.emit(page + 1)"
          class="px-2 py-0.5 rounded text-[11px] border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors text-fg-muted">
          Next
        </button>
      </div>
    }
  `,
})
export class PartitionDataTableComponent {
  @Input() data: Record<string, any>[] = [];
  @Input() total = 0;
  @Input() page = 1;
  @Input() totalPages = 0;
  @Input() loading = false;
  @Output() pageChange = new EventEmitter<number>();

  columns = computed(() => {
    if (this.data.length === 0) return [];
    return Object.keys(this.data[0]);
  });
}
