import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { MultiSelect } from 'primeng/multiselect';
import { Skeleton } from 'primeng/skeleton';
import { AssetCreate } from '../../models/asset.model';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [FormsModule, Select, TableModule, InputText, Card, Button, Tag, MultiSelect, Skeleton],
  templateUrl: './asset-list.component.html',
})
export class AssetListComponent implements OnInit {
  private router = inject(Router);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.assetService.assetTypes().map(t => t.name));

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  showCreateForm = signal(false);
  newAssetName = '';
  newAssetSymbol = '';
  newAssetDescription = '';
  newAssetTypeId = '';

  symbolTaken(): boolean {
    const sym = this.newAssetSymbol.trim().toLowerCase();
    if (!sym) return false;
    return this.assetService.assets().some(a => a.symbol?.toLowerCase() === sym);
  }

  ngOnInit(): void {
    this.assetService.loadAssets();
    this.assetService.loadAssetTypes();
  }

  navigateToAsset(id: string): void {
    this.router.navigate(['/settings/assets', id]);
  }

  openCreate(): void {
    this.newAssetName = '';
    this.newAssetSymbol = '';
    this.newAssetDescription = '';
    this.newAssetTypeId = this.assetService.assetTypes()[0]?.id ?? '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newAssetName.trim() || !this.newAssetSymbol.trim() || !this.newAssetTypeId || this.symbolTaken()) return;
    const data: AssetCreate = {
      asset_type_id: this.newAssetTypeId,
      name: this.newAssetName.trim(),
      symbol: this.newAssetSymbol.trim(),
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
