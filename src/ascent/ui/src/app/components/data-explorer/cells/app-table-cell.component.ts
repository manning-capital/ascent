import { Component, computed, inject, input } from '@angular/core';
import { map } from 'rxjs/operators';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import type { AppFetchFn } from '../../ui/data-table/app-column.model';
import { DataExplorerService } from '../../../services/data-explorer.service';

/** Server-paginated raw data view of the workspace's selected table.
 *
 *  Inherits the workspace filter context (table, time range, entity/descriptor/
 *  period filters) — there's no per-cell filtering in v1; the filter bar at the
 *  top of the workspace is the single source of truth. */
@Component({
  selector: 'app-table-cell',
  standalone: true,
  imports: [AppDataTableComponent],
  template: `
    @if (!table()) {
      <div class="flex-1 min-h-0 flex items-center justify-center text-fg-faint text-xs p-6">
        Select a data source.
      </div>
    } @else {
      <div class="flex-1 min-h-0" [style.min-height.px]="height()">
        <app-data-table
          [fetchPage]="fetchFn()"
          [autoColumns]="true"
          [autoLinks]="true"
          [gridLines]="true"
          storageKey="data-explorer-table-cell"
        />
      </div>
    }
  `,
})
export class AppTableCellComponent {
  table = input.required<string | null>();
  start = input<string | null>(null);
  end = input<string | null>(null);
  entityIds = input<string[]>([]);
  descriptorIds = input<string[]>([]);
  periodIds = input<string[]>([]);
  height = input<number>(360);

  private dataService = inject(DataExplorerService);

  fetchFn = computed<AppFetchFn<Record<string, any>> | null>(() => {
    const tbl = this.table();
    if (!tbl) return null;
    const start = this.start();
    const end = this.end();
    const entityIds = this.entityIds();
    const descriptorIds = this.descriptorIds();
    const periodIds = this.periodIds();
    return (page, pageSize, sort) => {
      const params: Record<string, any> = { table: tbl, page, page_size: pageSize };
      if (start) params['start'] = start;
      if (end) params['end'] = end;
      if (entityIds.length) params['entity_ids'] = entityIds;
      if (descriptorIds.length) params['descriptor_ids'] = descriptorIds;
      if (periodIds.length) params['period_ids'] = periodIds;
      params['sort_field'] = sort?.field ?? 'timestamp';
      params['sort_order'] = sort?.order ?? 'desc';
      return this.dataService
        .queryData(params)
        .pipe(map((res) => ({ items: res.items, total: res.total, columns: res.columns })));
    };
  });
}
