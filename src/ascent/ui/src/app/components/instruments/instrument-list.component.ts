import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InstrumentCreate } from '../../models/asset.model';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-instrument-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Card, Button, DataTableComponent],
  templateUrl: './instrument-list.component.html',
})
export class InstrumentListComponent implements OnInit {
  private router = inject(Router);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.assetService.instrumentTypes().map(t => t.display_name));

  /** Instruments enriched with type_display_name for filtering/sorting. */
  enrichedInstruments = computed(() => {
    const types = this.assetService.instrumentTypes();
    const typeMap = new Map(types.map(t => [t.id, t.display_name]));
    return this.assetService.instruments().map(inst => ({
      ...inst,
      type_display_name: typeMap.get(inst.instrument_type_id) ?? 'Unknown',
    }));
  });

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'name', header: 'Name', cellType: 'monospace', filterType: 'text' },
    { field: 'type_display_name', header: 'Type', cellType: 'link', linkRoute: (row: any) => `/settings/instrument-types/${row.instrument_type_id}`, filterType: 'select', filterOptions: this.typeNames },
    { field: 'pair', header: 'Pair', sortable: false, cellClass: 'text-surface-500', valueGetter: (p: any) => `${p.data?.from_asset_name ?? ''}/${p.data?.to_asset_name ?? ''}` },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToInstrument = (row: any) => ['/settings/instruments', row.id];

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

  typeRoute(typeId: string): string {
    return `/settings/instrument-types/${typeId}`;
  }
}
