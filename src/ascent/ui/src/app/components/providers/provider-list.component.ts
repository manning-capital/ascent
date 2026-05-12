import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Textarea } from 'primeng/textarea';
import { Button } from 'primeng/button';
import { ProviderCreate, ProviderListItem } from '../../models/provider.model';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';

@Component({
  selector: 'app-provider-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Textarea, Button, AppDataTableComponent, AppPageHeaderComponent],
  templateUrl: './provider-list.component.html',
})
export class ProviderListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  columns: AppColumn<ProviderListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    {
      field: 'provider_type_name',
      header: 'Type',
      cellType: 'link',
      linkRoute: (row: any) => `/settings/types/provider-types/${row.provider_type_id}`,
    },
    {
      field: 'provider_external_code',
      header: 'Code',
      cellType: 'monospace',
      format: (v) => v ?? '—',
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
  ];

  navigateToProvider = (row: ProviderListItem) => ['/settings/master-data/providers', row.id];

  fetchPage = computed<AppFetchFn<ProviderListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.providerService
        .loadProvidersPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total })));
    };
  });

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  newExternalCode = '';
  newUrl = '';

  ngOnInit(): void {
    this.providerService.loadProviderTypes();
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
    this.newDisplayName = '';
    this.newName = '';
    this.newDescription = '';
    this.newTypeId = this.providerService.providerTypes()[0]?.id ?? '';
    this.newExternalCode = '';
    this.newUrl = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newName.trim() || !this.newDisplayName.trim() || !this.newTypeId) return;
    const data: ProviderCreate = {
      provider_type_id: this.newTypeId,
      name: this.newName.trim(),
      display_name: this.newDisplayName.trim(),
      description: this.newDescription.trim() || null,
      provider_external_code: this.newExternalCode.trim() || null,
      url: this.newUrl.trim() || null,
    };
    this.providerService.createProvider(data).subscribe({
      next: () => {
        this.toast.success('Provider created');
        this.showCreateForm.set(false);
        this.search.update((s) => s);
      },
      error: () => this.toast.error('Failed to create provider'),
    });
  }
}
