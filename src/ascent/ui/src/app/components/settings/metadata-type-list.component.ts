import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { MetadataTypeItem } from '../../models/field.model';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';

@Component({
  selector: 'app-metadata-type-list',
  standalone: true,
  imports: [FormsModule, Button, InputText, Select, AppDataTableComponent, AppPageHeaderComponent],
  templateUrl: './metadata-type-list.component.html',
})
export class MetadataTypeListComponent implements OnInit {
  fieldService = inject(FieldService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  showCreateForm = signal(false);
  newName = '';
  newDisplayName = '';
  newDescription = '';
  newValueType = 'string';

  private valueTypeLabels: Record<string, string> = {
    string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean',
    date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference',
  };

  columns: AppColumn<MetadataTypeItem>[] = [
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'display_name', header: 'Display Name' },
    {
      field: 'value_type',
      header: 'Value Type',
      cellType: 'tag',
      tagMapper: (v): { label: string; severity: AppSeverity } => ({
        label: this.valueTypeLabels[v] ?? v,
        severity: 'secondary',
      }),
    },
    {
      field: 'is_active',
      header: 'Status',
      cellType: 'status',
      width: 112,
      pinned: 'right',
      tagMapper: (v): { label: string; severity: AppSeverity } => ({
        label: v ? 'Active' : 'Inactive',
        severity: v ? 'success' : 'secondary',
      }),
    },
    {
      field: 'description',
      header: 'Description',
      format: (v) => v || '—',
      cellClass: 'text-fg-faint',
    },
  ];

  navigateToMetadataType = (row: MetadataTypeItem) => ['/settings/types/metadata-types', row.id];

  fetchPage = computed<AppFetchFn<MetadataTypeItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.fieldService
        .loadMetadataTypesPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total })));
    };
  });

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    if (qp.get('search')) this.search.set(qp.get('search')!);
    if (qp.get('is_active') != null) this.statusFilter.set(qp.get('is_active') === 'true');
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.updateUrl();
  }

  onStatusChange(value: boolean | null): void {
    this.statusFilter.set(value);
    this.updateUrl();
  }

  clearFilters(): void {
    this.search.set('');
    this.statusFilter.set(null);
    this.updateUrl();
  }

  private updateUrl(): void {
    const queryParams: Record<string, any> = {};
    const search = this.search();
    if (search) queryParams['search'] = search;
    const isActive = this.statusFilter();
    if (isActive != null) queryParams['is_active'] = isActive;
    this.router.navigate([], { relativeTo: this.route, queryParams, replaceUrl: true });
  }

  openCreate(): void {
    this.newName = '';
    this.newDisplayName = '';
    this.newDescription = '';
    this.newValueType = 'string';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    const name = this.newName.trim();
    const displayName = this.newDisplayName.trim();
    if (!name || !displayName) return;
    this.fieldService.createMetadataType({
      name,
      display_name: displayName,
      description: this.newDescription.trim() || undefined,
      value_type: this.newValueType,
    }).subscribe({
      next: () => {
        this.toast.success('Metadata type created');
        this.showCreateForm.set(false);
        this.search.update((s) => s);
      },
      error: () => this.toast.error('Failed to create metadata type'),
    });
  }
}
