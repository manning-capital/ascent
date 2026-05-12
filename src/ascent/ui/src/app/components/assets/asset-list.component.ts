import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Button } from 'primeng/button';
import { AssetCreate, AssetListItem } from '../../models/asset.model';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Button, AppDataTableComponent, AppPageHeaderComponent],
  templateUrl: './asset-list.component.html',
})
export class AssetListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  typeNames = computed(() => this.assetService.assetTypes().map((t) => t.display_name));

  columns: AppColumn<AssetListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    {
      field: 'asset_type_name',
      header: 'Type',
      cellType: 'link',
      linkRoute: (row: any) => `/settings/types/asset-types/${row.asset_type_id}`,
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

  navigateToAsset = (row: AssetListItem) => ['/settings/master-data/assets', row.id];

  fetchPage = computed<AppFetchFn<AssetListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.assetService
        .loadAssetsPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total })));
    };
  });

  showCreateForm = signal(false);
  newAssetDisplayName = '';
  newAssetName = '';
  newAssetDescription = '';
  newAssetTypeId = '';

  ngOnInit(): void {
    this.assetService.loadAssetTypes();
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
    this.newAssetDisplayName = '';
    this.newAssetName = '';
    this.newAssetDescription = '';
    this.newAssetTypeId = this.assetService.assetTypes()[0]?.id ?? '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newAssetDisplayName.trim() || !this.newAssetName.trim() || !this.newAssetTypeId) return;
    const data: AssetCreate = {
      asset_type_id: this.newAssetTypeId,
      name: this.newAssetName.trim(),
      display_name: this.newAssetDisplayName.trim(),
      description: this.newAssetDescription.trim() || null,
    };
    this.assetService.createAsset(data).subscribe({
      next: () => {
        this.toast.success('Asset created');
        this.showCreateForm.set(false);
        this.search.update((s) => s);
      },
      error: () => this.toast.error('Failed to create asset'),
    });
  }
}
