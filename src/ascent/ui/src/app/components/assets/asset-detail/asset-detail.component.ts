import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, MetadataHistoryEntry, AssetTypeMetadataField } from '../../../models/asset.model';
import { LoadingSpinnerComponent } from '../../shared/loading-spinner.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Select } from 'primeng/select';
import { Checkbox } from 'primeng/checkbox';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { ConfirmationService } from 'primeng/api';

@Component({
  selector: 'app-asset-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    LoadingSpinnerComponent,
    Tabs, TabList, Tab,
    Select,
    Checkbox,
    DatePicker,
    TableModule,
  ],
  templateUrl: './asset-detail.component.html',
})
export class AssetDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private toast = inject(ToastService);
  private confirmationService = inject(ConfirmationService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);

  tabs = ['Overview', 'Metadata', 'Provider Mappings'];
  activeTab = signal('Overview');

  assetId = '';

  // Edit state
  editing = signal(false);
  editName = '';
  editSymbol = '';
  editDescription = '';
  editIsActive = true;

  // Metadata state
  metadataEntries = signal<MetadataEntry[]>([]);
  assetTypeFields = signal<AssetTypeMetadataField[]>([]);
  fieldInputValues: Record<string, string> = {};
  fieldTimestampValues: Record<string, Date | null> = {};
  showMetadataForm = signal(false);
  newMetadataId = '';
  newMetadataValue = '';
  newMetadataTimestamp: Date | null = null;

  // History state
  historyMetadataId = signal<string | null>(null);
  historyMetadataName = signal('');
  historyEntries = signal<MetadataHistoryEntry[]>([]);
  editingHistoryTimestamp = signal<string | null>(null);
  editHistoryValue = '';
  editHistoryTimestamp: Date | null = null;

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.assetId) return;
      this.assetId = id;

      this.activeTab.set('Overview');
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.assetTypeFields.set([]);
      this.showMetadataForm.set(false);
      this.historyMetadataId.set(null);
      this.historyEntries.set([]);

      this.assetService.loadAssetDetail(this.assetId);
      this.assetService.loadMetadataTypes();
      this.loadMetadata();
      this.loadAssetTypeFields();
    });
  }

  private loadAssetTypeFields(): void {
    const check = () => {
      const asset = this.assetService.selectedAsset();
      if (asset) {
        this.assetService.getAssetTypeMetadata(asset.asset_type_id).subscribe({
          next: fields => this.assetTypeFields.set(fields),
        });
      } else {
        setTimeout(check, 100);
      }
    };
    check();
  }

  // ---- Edit ----

  startEdit(): void {
    const asset = this.assetService.selectedAsset();
    if (!asset) return;
    this.editName = asset.name;
    this.editSymbol = asset.symbol ?? '';
    this.editDescription = asset.description ?? '';
    this.editIsActive = asset.is_active;
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  submitEdit(): void {
    if (!this.editName.trim()) return;
    this.assetService.updateAsset(this.assetId, {
      name: this.editName.trim(),
      symbol: this.editSymbol.trim() || null,
      description: this.editDescription.trim() || null,
      is_active: this.editIsActive,
    }).subscribe({
      next: () => {
        this.toast.success('Asset updated');
        this.editing.set(false);
        this.assetService.loadAssetDetail(this.assetId, true);
      },
      error: () => this.toast.error('Failed to update asset'),
    });
  }

  deleteAsset(): void {
    this.confirmationService.confirm({
      header: 'Delete Asset',
      message: 'Are you sure you want to delete this asset? This action cannot be undone.',
      acceptLabel: 'Delete',
      rejectLabel: 'Cancel',
      accept: () => {
        this.assetService.deleteAsset(this.assetId).subscribe({
          next: () => {
            this.toast.success('Asset deleted');
            window.history.back();
          },
          error: () => this.toast.error('Failed to delete asset'),
        });
      },
    });
  }

  // ---- Metadata ----

  loadMetadata(): void {
    this.assetService.getAssetMetadata(this.assetId).subscribe({
      next: entries => this.metadataEntries.set(entries),
    });
  }

  fieldValue(metadataId: string): any {
    const entry = this.metadataEntries().find(e => e.metadata_id === metadataId);
    return entry?.value ?? null;
  }

  extraMetadata(): MetadataEntry[] {
    const fieldIds = new Set(this.assetTypeFields().map(f => f.metadata_id));
    return this.metadataEntries().filter(e => !fieldIds.has(e.metadata_id));
  }

  openMetadataForm(): void {
    const usedIds = new Set([
      ...this.assetTypeFields().map(f => f.metadata_id),
      ...this.metadataEntries().map(e => e.metadata_id),
    ]);
    const available = this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id));
    this.newMetadataId = available[0]?.id ?? this.assetService.metadataTypes()[0]?.id ?? '';
    this.newMetadataValue = '';
    this.newMetadataTimestamp = null;
    this.showMetadataForm.set(true);
  }

  cancelMetadataForm(): void {
    this.showMetadataForm.set(false);
  }

  submitMetadata(): void {
    if (!this.newMetadataId || !this.newMetadataValue) return;
    let value: any = this.newMetadataValue;
    try { value = JSON.parse(this.newMetadataValue); } catch {}
    const payload: any = { metadata_id: this.newMetadataId, value };
    if (this.newMetadataTimestamp) {
      payload.timestamp = this.newMetadataTimestamp.toISOString();
    }
    this.assetService.addAssetMetadata(this.assetId, payload).subscribe({
      next: () => {
        this.toast.success('Metadata added');
        this.showMetadataForm.set(false);
        this.loadMetadata();
        this.assetService.loadAssetDetail(this.assetId, true);
      },
      error: () => this.toast.error('Failed to add metadata'),
    });
  }

  submitFieldValue(field: AssetTypeMetadataField): void {
    const rawValue = this.fieldInputValues[field.metadata_id] ?? '';
    if (!rawValue && rawValue !== '0') return;
    let value: any = rawValue;
    if (field.value_type === 'number') {
      value = Number(rawValue);
      if (isNaN(value)) return;
    } else if (field.value_type === 'boolean') {
      value = rawValue === 'true';
    } else if (field.value_type === 'json') {
      try { value = JSON.parse(rawValue); } catch { return; }
    }
    const payload: any = { metadata_id: field.metadata_id, value };
    const ts = this.fieldTimestampValues[field.metadata_id];
    if (ts) {
      payload.timestamp = ts.toISOString();
    }
    this.assetService.addAssetMetadata(this.assetId, payload).subscribe({
      next: () => {
        this.toast.success(`${field.metadata_name} updated`);
        this.fieldInputValues[field.metadata_id] = '';
        this.fieldTimestampValues[field.metadata_id] = null;
        this.loadMetadata();
        this.assetService.loadAssetDetail(this.assetId, true);
        if (this.historyMetadataId() === field.metadata_id) {
          this.refreshHistory();
        }
      },
      error: () => this.toast.error(`Failed to update ${field.metadata_name}`),
    });
  }

  deleteMetadata(entry: MetadataEntry): void {
    this.assetService.deleteAssetMetadata(this.assetId, entry.metadata_id).subscribe({
      next: () => {
        this.toast.success('Metadata removed');
        this.loadMetadata();
        this.assetService.loadAssetDetail(this.assetId, true);
      },
      error: () => this.toast.error('Failed to remove metadata'),
    });
  }

  deleteFieldMetadata(metadataId: string): void {
    this.assetService.deleteAssetMetadata(this.assetId, metadataId).subscribe({
      next: () => {
        this.toast.success('Value cleared');
        this.loadMetadata();
        if (this.historyMetadataId() === metadataId) {
          this.refreshHistory();
        }
      },
      error: () => this.toast.error('Failed to clear value'),
    });
  }

  showHistory(entry: MetadataEntry): void {
    this.historyMetadataId.set(entry.metadata_id);
    this.historyMetadataName.set(entry.metadata_name);
    this.editingHistoryTimestamp.set(null);
    this.assetService.getAssetMetadataHistory(this.assetId, entry.metadata_id).subscribe({
      next: entries => this.historyEntries.set(entries),
    });
  }

  showFieldHistory(field: AssetTypeMetadataField): void {
    this.historyMetadataId.set(field.metadata_id);
    this.historyMetadataName.set(field.metadata_name);
    this.editingHistoryTimestamp.set(null);
    this.assetService.getAssetMetadataHistory(this.assetId, field.metadata_id).subscribe({
      next: entries => this.historyEntries.set(entries),
    });
  }

  closeHistory(): void {
    this.historyMetadataId.set(null);
    this.historyEntries.set([]);
    this.editingHistoryTimestamp.set(null);
  }

  private refreshHistory(): void {
    const metaId = this.historyMetadataId();
    if (!metaId) return;
    this.assetService.getAssetMetadataHistory(this.assetId, metaId).subscribe({
      next: entries => this.historyEntries.set(entries),
    });
  }

  // ---- History editing ----

  startEditHistory(h: MetadataHistoryEntry): void {
    this.editingHistoryTimestamp.set(h.timestamp);
    this.editHistoryValue = typeof h.value === 'object' ? JSON.stringify(h.value) : String(h.value);
    this.editHistoryTimestamp = new Date(h.timestamp);
  }

  cancelEditHistory(): void {
    this.editingHistoryTimestamp.set(null);
  }

  submitEditHistory(): void {
    const metaId = this.historyMetadataId();
    const origTs = this.editingHistoryTimestamp();
    if (!metaId || !origTs) return;
    let value: any = this.editHistoryValue;
    try { value = JSON.parse(this.editHistoryValue); } catch {}
    const newTs = this.editHistoryTimestamp ? this.editHistoryTimestamp.toISOString() : undefined;
    this.assetService.updateAssetMetadataEntry(this.assetId, metaId, origTs, {
      value,
      timestamp: newTs,
    }).subscribe({
      next: () => {
        this.toast.success('Entry updated');
        this.editingHistoryTimestamp.set(null);
        this.refreshHistory();
        this.loadMetadata();
      },
      error: () => this.toast.error('Failed to update entry'),
    });
  }

  deleteHistoryEntry(h: MetadataHistoryEntry): void {
    const metaId = this.historyMetadataId();
    if (!metaId) return;
    this.assetService.deleteAssetMetadataEntry(this.assetId, metaId, h.timestamp).subscribe({
      next: () => {
        this.toast.success('Entry deleted');
        this.refreshHistory();
        this.loadMetadata();
      },
      error: () => this.toast.error('Failed to delete entry'),
    });
  }

  // ---- Helpers ----

  formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
}
