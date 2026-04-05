import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { Router } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Paginator } from 'primeng/paginator';
import { EmptyStateComponent } from './empty-state.component';
import { Skeleton } from 'primeng/skeleton';

/** Maps display column names to their ID column and route prefix. */
const LINK_COLUMNS: Record<string, { idCol: string; route: string }> = {
  provider: { idCol: 'provider_id', route: '/settings/providers' },
  from_asset: { idCol: 'from_asset_id', route: '/settings/assets' },
  to_asset: { idCol: 'to_asset_id', route: '/settings/assets' },
  asset: { idCol: 'asset_id', route: '/settings/assets' },
  instrument: { idCol: 'instrument_id', route: '/settings/instruments' },
  composite: { idCol: 'composite_id', route: '/settings/composites' },
  attribute: { idCol: 'attribute_id', route: '/settings/attributes' },
  metadata: { idCol: 'metadata_id', route: '/settings/metadata-types' },
};

/** Columns that should be visually highlighted as key/identifier columns. */
const KEY_COLUMNS = new Set(['timestamp']);

/** Columns that are raw IDs and should be hidden from the table. */
const HIDDEN_COLUMNS = new Set([
  'provider_id', 'from_asset_id', 'to_asset_id', 'asset_id', 'period_id',
  'instrument_id', 'composite_id', 'attribute_id', 'metadata_id',
]);

@Component({
  selector: 'app-partition-data-table',
  standalone: true,
  imports: [TableModule, Paginator, EmptyStateComponent, Skeleton],
  styles: [`
    :host { display: flex; flex-direction: column; min-height: 0; }
    :host ::ng-deep .p-datatable td a { pointer-events: all; position: relative; z-index: 1; }
    :host ::ng-deep .p-datatable td.key-col { background: color-mix(in srgb, var(--fg) 4%, transparent); }
    :host ::ng-deep .p-datatable th.key-col { background: color-mix(in srgb, var(--fg) 7%, transparent); }
  `],
  template: `
    @if (data.length === 0 && !isLoading) {
      <div class="flex items-center justify-center flex-1">
        <app-empty-state title="No partition data" message="This partition has no data rows yet." icon="data"/>
      </div>
    } @else if (isLoading && data.length === 0) {
      <div class="flex-1 flex flex-col min-h-0">
        <div class="flex gap-3 px-3 py-2.5 border-b border-edge">
          @for (_ of [1,2,3,4,5]; track $index) {
            <p-skeleton height="1rem" class="flex-1"/>
          }
        </div>
        <div class="flex-1 flex flex-col overflow-hidden">
          @for (_ of skeletonRows; track $index) {
            <div class="flex gap-3 px-3 py-2.5 border-b border-edge-dim">
              @for (_ of [1,2,3,4,5]; track $index) {
                <p-skeleton height="0.875rem" class="flex-1"/>
              }
            </div>
          }
        </div>
        <div class="shrink-0 flex items-center justify-between px-3 py-2 border-t border-edge">
          <p-skeleton width="10rem" height="1.25rem"/>
          <div class="flex gap-1.5">
            @for (_ of [1,2,3]; track $index) {
              <p-skeleton width="2rem" height="2rem" borderRadius="6px"/>
            }
          </div>
          <p-skeleton width="8rem" height="1.25rem"/>
        </div>
      </div>
    } @else {
      <div class="flex-1 overflow-y-auto min-h-0 text-[11px] transition-opacity duration-200 rounded-lg border border-surface overflow-hidden" [class.opacity-40]="isLoading" [class.pointer-events-none]="isLoading">
        <p-table [value]="data" [lazy]="true" (onLazyLoad)="onSort($event)" [sortField]="sortField" [sortOrder]="sortOrder">
          <ng-template #header>
            <tr>
              @for (col of columns; track col) {
                <th class="whitespace-nowrap" [class.key-col]="isKeyColumn(col)" [pSortableColumn]="col">{{ formatHeader(col) }} <p-sortIcon [field]="col"/></th>
              }
            </tr>
          </ng-template>
          <ng-template #body let-row>
            <tr>
              @for (col of columns; track col) {
                <td class="whitespace-nowrap font-mono" [class.key-col]="isKeyColumn(col)">
                  @if (isLinkColumn(col)) {
                    <a (click)="$event.stopPropagation(); navigateToEntity(col, row)" class="text-primary hover:underline cursor-pointer relative z-10">{{ row[col] ?? '-' }}</a>
                  } @else {
                    {{ row[col] ?? '-' }}
                  }
                </td>
              }
            </tr>
          </ng-template>
        </p-table>
      </div>

      <p-paginator
        [rows]="pageSize"
        [totalRecords]="total"
        [first]="(page - 1) * pageSize"
        [rowsPerPageOptions]="[25, 50, 100]"
        (onPageChange)="onPageEvent($event)"
        class="shrink-0"/>
    }
  `,
})
export class PartitionDataTableComponent {
  @Input() data: Record<string, any>[] = [];
  @Input() total = 0;
  @Input() page = 1;
  @Input() pageSize = 25;
  @Input() totalPages = 0;
  @Input() loading = false;
  @Input() sortField: string = 'timestamp';
  @Input() sortOrder: number = -1;  // -1 = desc, 1 = asc
  skeletonRows = Array.from({ length: 20 });
  @Output() pageChange = new EventEmitter<number>();
  @Output() pageSizeChange = new EventEmitter<number>();
  @Output() sortChange = new EventEmitter<{ field: string; order: number }>();

  private router = inject(Router);

  /** True when the parent loading flag is set. */
  get isLoading(): boolean {
    return this.loading;
  }

  /** Visible columns — filters out raw ID columns. */
  get columns(): string[] {
    if (this.data.length === 0) return [];
    return Object.keys(this.data[0]).filter(col => !HIDDEN_COLUMNS.has(col));
  }

  /** Format a column key into a capitalized header label. */
  formatHeader(col: string): string {
    return col
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  /** Whether this column should be visually highlighted as a key column. */
  isKeyColumn(col: string): boolean {
    return KEY_COLUMNS.has(col) || this.isLinkColumn(col);
  }

  /** Whether this column should render as a link. */
  isLinkColumn(col: string): boolean {
    const cfg = LINK_COLUMNS[col];
    if (!cfg) return false;
    return this.data.length > 0 && this.data[0][cfg.idCol] !== undefined;
  }

  /** Navigate to the entity detail page for a linked column. */
  navigateToEntity(col: string, row: Record<string, any>): void {
    const cfg = LINK_COLUMNS[col];
    if (cfg) {
      this.router.navigate([cfg.route, row[cfg.idCol]]);
    }
  }

  onSort(event: any): void {
    if (event.sortField && event.sortField !== this.sortField || event.sortOrder !== this.sortOrder) {
      this.sortChange.emit({ field: event.sortField, order: event.sortOrder });
    }
  }

  onPageEvent(event: any): void {
    const newPageSize = event.rows;
    const newPage = (event.page ?? 0) + 1;
    if (newPageSize !== this.pageSize) {
      this.pageSizeChange.emit(newPageSize);
    }
    this.pageChange.emit(newPage);
  }
}
