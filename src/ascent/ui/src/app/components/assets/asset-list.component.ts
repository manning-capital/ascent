import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { AssetCreate, AssetListItem } from '../../models/asset.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Card, Button, ServerTableComponent],
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

  typeNames = computed(() => this.assetService.assetTypes().map(t => t.display_name));

  columns: DataTableColumn<AssetListItem>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'asset_type_name', header: 'Type', cellType: 'link', linkRoute: (row: any) => `/settings/asset-types/${row.asset_type_id}` },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112 },
  ];

  navigateToAsset = (row: any) => ['/settings/assets', row.id];

  fetchPage = computed<ServerFetchFn<AssetListItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.assetService.loadAssetsPaginated(page, pageSize, filters, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
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
        // Trigger refetch by toggling a filter signal
        this.search.update(s => s);
      },
      error: () => this.toast.error('Failed to create asset'),
    });
  }
}
