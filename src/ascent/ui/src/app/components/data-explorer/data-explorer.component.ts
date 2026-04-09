import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { DataExplorerService } from '../../services/data-explorer.service';
import type { ServerFetchFn } from '../shared/data-table/data-table.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import { Select } from 'primeng/select';
import { MultiSelect } from 'primeng/multiselect';
import { DatePicker } from 'primeng/datepicker';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-data-explorer',
  standalone: true,
  imports: [
    FormsModule,
    Select,
    MultiSelect,
    DatePicker,
    Button,
    Card,
    Skeleton,
    ServerTableComponent,
  ],
  templateUrl: './data-explorer.component.html',
})
export class DataExplorerComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  dataService = inject(DataExplorerService);

  selectedTable = signal<string | null>(null);
  startDate = signal<Date | null>(null);
  endDate = signal<Date | null>(null);
  selectedEntityIds = signal<string[]>([]);
  selectedDescriptorIds = signal<string[]>([]);
  selectedPeriodIds = signal<string[]>([]);
  page = signal(1);
  pageSize = signal(25);

  fetchPageFn = computed<ServerFetchFn<Record<string, any>> | null>(() => {
    const table = this.selectedTable();
    if (!table) return null;
    const start = this.startDate();
    const end = this.endDate();
    const entityIds = this.selectedEntityIds();
    const descriptorIds = this.selectedDescriptorIds();
    const periodIds = this.selectedPeriodIds();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const params: Record<string, any> = { table, page, page_size: pageSize };
      if (start) params['start'] = start.toISOString();
      if (end) params['end'] = end.toISOString();
      if (entityIds.length) params['entity_ids'] = entityIds;
      if (descriptorIds.length) params['descriptor_ids'] = descriptorIds;
      if (periodIds.length) params['period_ids'] = periodIds;
      params['sort_field'] = sort?.field ?? 'timestamp';
      params['sort_order'] = sort?.order ?? 'desc';
      return this.dataService.queryData(params).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  /** Whether the selected table has a period dimension. */
  hasPeriod(): boolean {
    const table = this.selectedTable();
    if (!table) return false;
    const source = this.dataService.dataSources().find(s => s.table === table);
    return source?.has_period ?? false;
  }

  /** Label for the entity filter based on selected table's entity type. */
  entityLabel(): string {
    const table = this.selectedTable();
    if (!table) return 'Entities';
    const source = this.dataService.dataSources().find(s => s.table === table);
    if (!source) return 'Entities';
    return source.entity_type.charAt(0).toUpperCase() + source.entity_type.slice(1) + 's';
  }

  /** Label for the descriptor filter based on selected table's descriptor type. */
  descriptorLabel(): string {
    const table = this.selectedTable();
    if (!table) return 'Fields';
    const source = this.dataService.dataSources().find(s => s.table === table);
    if (!source) return 'Fields';
    return source.descriptor_type.charAt(0).toUpperCase() + source.descriptor_type.slice(1) + 's';
  }

  ngOnInit(): void {
    this.dataService.loadSources();

    // Restore from URL query params
    const qp = this.route.snapshot.queryParamMap;

    const table = qp.get('table');
    if (table) {
      this.selectedTable.set(table);
      this.dataService.loadFilterOptions(table);
    }

    const start = qp.get('start');
    if (start) this.startDate.set(new Date(start));
    const end = qp.get('end');
    if (end) this.endDate.set(new Date(end));

    const entityIds = qp.getAll('entity_ids');
    if (entityIds.length) this.selectedEntityIds.set(entityIds);
    const descriptorIds = qp.getAll('descriptor_ids');
    if (descriptorIds.length) this.selectedDescriptorIds.set(descriptorIds);
    const periodIds = qp.getAll('period_ids');
    if (periodIds.length) this.selectedPeriodIds.set(periodIds);

    const pg = qp.get('page');
    if (pg) this.page.set(parseInt(pg, 10) || 1);
    const ps = qp.get('page_size');
    if (ps) this.pageSize.set(parseInt(ps, 10) || 25);

    if (table) {
      this.updateUrl();
    }
  }

  onTableChange(table: string): void {
    this.selectedTable.set(table);
    this.selectedEntityIds.set([]);
    this.selectedDescriptorIds.set([]);
    this.selectedPeriodIds.set([]);
    this.page.set(1);
    this.dataService.loadFilterOptions(table);
    this.updateUrl();
  }

  onFilterChange(): void {
    this.page.set(1);
    this.updateUrl();
  }

  onPageChange(page: number): void {
    this.page.set(page);
    this.updateUrl();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.updateUrl();
  }

  clearFilters(): void {
    this.startDate.set(null);
    this.endDate.set(null);
    this.selectedEntityIds.set([]);
    this.selectedDescriptorIds.set([]);
    this.selectedPeriodIds.set([]);
    this.page.set(1);
    this.updateUrl();
  }

  private updateUrl(): void {
    const table = this.selectedTable();
    if (!table) return;

    const queryParams: Record<string, any> = { table, page: this.page(), page_size: this.pageSize() };
    const start = this.startDate();
    if (start) queryParams['start'] = start.toISOString();
    const end = this.endDate();
    if (end) queryParams['end'] = end.toISOString();
    const entityIds = this.selectedEntityIds();
    if (entityIds.length) queryParams['entity_ids'] = entityIds;
    const descriptorIds = this.selectedDescriptorIds();
    if (descriptorIds.length) queryParams['descriptor_ids'] = descriptorIds;
    const periodIds = this.selectedPeriodIds();
    if (periodIds.length) queryParams['period_ids'] = periodIds;

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }
}
