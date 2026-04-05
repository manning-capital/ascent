import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DataExplorerService } from '../../services/data-explorer.service';
import { DataSourceInfo } from '../../models/data-explorer.model';
import { PartitionDataTableComponent } from '../shared/partition-data-table.component';
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
    DecimalPipe,
    FormsModule,
    Select,
    MultiSelect,
    DatePicker,
    Button,
    Card,
    Skeleton,
    PartitionDataTableComponent,
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
  sortField = signal('timestamp');
  sortOrder = signal<number>(-1);

  private isSyncingFromUrl = false;

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
    this.isSyncingFromUrl = true;

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

    this.isSyncingFromUrl = false;

    if (table) {
      this.loadData();
    }
  }

  onTableChange(table: string): void {
    this.selectedTable.set(table);
    this.selectedEntityIds.set([]);
    this.selectedDescriptorIds.set([]);
    this.selectedPeriodIds.set([]);
    this.page.set(1);
    this.dataService.loadFilterOptions(table);
    this.loadData();
  }

  onFilterChange(): void {
    this.page.set(1);
    this.loadData();
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.loadData();
  }

  onSortChange(event: { field: string; order: number }): void {
    this.sortField.set(event.field);
    this.sortOrder.set(event.order);
    this.page.set(1);
    this.loadData();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
    this.loadData();
  }

  clearFilters(): void {
    this.startDate.set(null);
    this.endDate.set(null);
    this.selectedEntityIds.set([]);
    this.selectedDescriptorIds.set([]);
    this.selectedPeriodIds.set([]);
    this.page.set(1);
    this.loadData();
  }

  loadData(): void {
    const table = this.selectedTable();
    if (!table) return;

    const params: Record<string, any> = {
      table,
      page: this.page(),
      page_size: this.pageSize(),
    };

    const start = this.startDate();
    if (start) params['start'] = start.toISOString();
    const end = this.endDate();
    if (end) params['end'] = end.toISOString();

    const entityIds = this.selectedEntityIds();
    if (entityIds.length) params['entity_ids'] = entityIds;
    const descriptorIds = this.selectedDescriptorIds();
    if (descriptorIds.length) params['descriptor_ids'] = descriptorIds;
    const periodIds = this.selectedPeriodIds();
    if (periodIds.length) params['period_ids'] = periodIds;

    params['sort_field'] = this.sortField();
    params['sort_order'] = this.sortOrder() === 1 ? 'asc' : 'desc';

    this.dataService.loadData(params);
    this.updateUrl(params);
  }

  private updateUrl(params: Record<string, any>): void {
    const queryParams: Record<string, any> = { table: params['table'] };
    if (params['start']) queryParams['start'] = params['start'];
    if (params['end']) queryParams['end'] = params['end'];
    if (params['entity_ids']) queryParams['entity_ids'] = params['entity_ids'];
    if (params['descriptor_ids']) queryParams['descriptor_ids'] = params['descriptor_ids'];
    if (params['period_ids']) queryParams['period_ids'] = params['period_ids'];
    if (params['page'] > 1) queryParams['page'] = params['page'];
    if (params['page_size'] !== 25) queryParams['page_size'] = params['page_size'];

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }
}
