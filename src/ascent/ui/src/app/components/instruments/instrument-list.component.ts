import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { InstrumentCreate } from '../../models/asset.model';

@Component({
  selector: 'app-instrument-list',
  standalone: true,
  imports: [FormsModule, Select, TableModule, InputText, Card, Button, Tag, Skeleton],
  templateUrl: './instrument-list.component.html',
})
export class InstrumentListComponent implements OnInit {
  private router = inject(Router);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.assetService.instrumentTypes().map(t => t.name));

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  newProviderId = '';
  newFromAssetId = '';
  newToAssetId = '';

  nameTaken(): boolean {
    const n = this.newName.trim().toLowerCase();
    if (!n) return false;
    return this.assetService.instruments().some(i => i.name?.toLowerCase() === n);
  }

  ngOnInit(): void {
    this.assetService.loadInstruments();
    this.assetService.loadInstrumentTypes();
    this.assetService.loadAssets();
    this.providerService.loadProviders();
  }

  navigateToInstrument(id: string): void {
    this.router.navigate(['/settings/instruments', id]);
  }

  openCreate(): void {
    this.newDisplayName = '';
    this.newName = '';
    this.newDescription = '';
    this.newTypeId = this.assetService.instrumentTypes()[0]?.id ?? '';
    this.newProviderId = this.providerService.providers()[0]?.id ?? '';
    this.newFromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.newToAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newDisplayName.trim() || !this.newName.trim() || !this.newTypeId || !this.newProviderId || !this.newFromAssetId || !this.newToAssetId || this.nameTaken()) return;
    const data: InstrumentCreate = {
      name: this.newName.trim(),
      display_name: this.newDisplayName.trim(),
      instrument_type_id: this.newTypeId,
      provider_id: this.newProviderId,
      from_asset_id: this.newFromAssetId,
      to_asset_id: this.newToAssetId,
      description: this.newDescription.trim() || undefined,
    };
    this.assetService.createInstrument(data).subscribe({
      next: () => {
        this.toast.success('Instrument created');
        this.showCreateForm.set(false);
        this.assetService.loadInstruments();
      },
      error: () => this.toast.error('Failed to create instrument'),
    });
  }

  getTypeName(typeId: string): string {
    return this.assetService.instrumentTypes().find(t => t.id === typeId)?.name ?? 'Unknown';
  }
}
