import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { AssetCreate } from '../../models/asset.model';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Card, Button, DataTableComponent],
  templateUrl: './asset-list.component.html',
})
export class AssetListComponent implements OnInit {
  private router = inject(Router);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.assetService.assetTypes().map(t => t.display_name));

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'name', header: 'Name', cellType: 'monospace', filterType: 'text' },
    { field: 'asset_type_name', header: 'Type', cellType: 'link', linkRoute: (row: any) => `/settings/asset-types/${row.asset_type_id}`, filterType: 'select', filterOptions: this.typeNames },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToAsset = (row: any) => ['/settings/assets', row.id];

  showCreateForm = signal(false);
  newAssetDisplayName = '';
  newAssetName = '';
  newAssetDescription = '';
  newAssetTypeId = '';

  nameTaken(): boolean {
    const n = this.newAssetName.trim().toLowerCase();
    if (!n) return false;
    return this.assetService.assets().some(a => a.name?.toLowerCase() === n);
  }

  ngOnInit(): void {
    this.assetService.loadAssets();
    this.assetService.loadAssetTypes();
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
    if (!this.newAssetDisplayName.trim() || !this.newAssetName.trim() || !this.newAssetTypeId || this.nameTaken()) return;
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
        this.assetService.loadAssets();
      },
      error: () => this.toast.error('Failed to create asset'),
    });
  }
}
