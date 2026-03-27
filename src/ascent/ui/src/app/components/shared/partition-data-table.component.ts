import { Component, Input, Output, EventEmitter, computed } from '@angular/core';
import { TableModule } from 'primeng/table';

@Component({
  selector: 'app-partition-data-table',
  standalone: true,
  imports: [TableModule],
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

      <!-- Table — scrollable with sticky header via PrimeNG -->
      <div class="flex-1 min-h-0 text-[11px]">
        <p-table [value]="data" [scrollable]="true" scrollHeight="flex">
          <ng-template #header>
            <tr>
              @for (col of columns(); track col) {
                <th class="whitespace-nowrap">{{ col }}</th>
              }
            </tr>
          </ng-template>
          <ng-template #body let-row>
            <tr>
              @for (col of columns(); track col) {
                <td class="whitespace-nowrap font-mono">{{ row[col] ?? '-' }}</td>
              }
            </tr>
          </ng-template>
          <ng-template #emptymessage>
            <tr>
              <td [attr.colspan]="columns().length">No data.</td>
            </tr>
          </ng-template>
        </p-table>
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
