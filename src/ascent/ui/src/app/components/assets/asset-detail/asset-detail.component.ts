import { Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, AssetTypeMetadataField, AssetTypeProviderAssetMetadataField, MetadataHistoryGrid, BulkHistoryUpdate, ProviderAssetLink } from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Skeleton } from 'primeng/skeleton';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-asset-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    Select,
    DatePicker,
    TableModule,
    Tag,
    Button,
    InputText,
    Skeleton,
    Tabs, TabList, Tab,
    Panel,
    MetadataHistoryTableComponent,
    SafeDeleteDialogComponent,
    FieldPanelComponent,
  ],
  templateUrl: './asset-detail.component.html',
})
export class AssetDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private fieldService = inject(FieldService);

  assetId = '';

  // Type lookup
  assetType = computed(() => {
    const asset = this.assetService.selectedAsset();
    if (!asset) return null;
    return this.assetService.assetTypes().find(t => t.id === asset.asset_type_id) ?? null;
  });

  // General panel fields
  generalFields = computed<PanelField[]>(() => {
    const asset = this.assetService.selectedAsset();
    const aType = this.assetType();
    if (!asset) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: asset.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: asset.display_name },
      { type: 'link', key: 'type', label: 'Type', value: aType?.display_name ?? aType?.name ?? null, route: aType ? ['/settings/asset-types', aType.id] : [], fallback: '-',
        options: this.assetService.assetTypes().map(t => ({ label: t.display_name || t.name, value: t.id })) },
      { type: 'active', key: 'isActive', label: 'Active', value: asset.is_active },
      { type: 'date', key: 'createdAt', label: 'Created', value: asset.created_at },
      { type: 'text', key: 'description', label: 'Description', value: asset.description },
    ];
  });
  generalEditValues = signal<Record<string, any>>({});

  // Metadata panel fields
  metadataFields = computed<PanelField[]>(() => {
    const fields = this.assetTypeFields();
    const entries = this.metadataEntries();
    return fields.map(field => {
      const entry = entries.find(e => e.metadata_id === field.metadata_id);
      const base = {
        key: field.metadata_id,
        label: field.metadata_display_name || field.metadata_name,
        required: field.is_required,
        inherited: field.is_inherited,
        subtitle: entry?.timestamp ? `as of ${new Date(entry.timestamp).toLocaleDateString()}` : undefined,
      };
      const val = entry?.value ?? null;
      switch (field.value_type) {
        case 'boolean': return { ...base, type: 'boolean' as const, value: val, fallback: 'Not set' };
        case 'integer': return { ...base, type: 'number' as const, value: val, step: 1, fallback: 'Not set' };
        case 'float': return { ...base, type: 'number' as const, value: val, step: 0.01, fallback: 'Not set' };
        case 'date': return { ...base, type: 'text' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
        case 'time': return { ...base, type: 'time' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
        case 'datetime': return { ...base, type: 'datetime' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
        default: return { ...base, type: 'text' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
      }
    });
  });
  metadataEditValues = signal<Record<string, any>>({});

  // Tabs
  tabs = ['Details', 'History', 'Settings'];
  activeTab = signal('Details');

  // Delete
  showDeleteDialog = signal(false);
  deleteUsage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  // Edit state
  editing = signal(false);
  editDisplayName = '';
  editName = '';
  editDescription = '';
  editAssetTypeId = '';
  editIsActive = true;
  editTimestamp: Date = new Date();
  editFieldValues: Record<string, string> = {};
  editPAFieldValues: Record<string, string> = {};

  // Metadata state
  metadataEntries = signal<MetadataEntry[]>([]);
  assetTypeFields = signal<AssetTypeMetadataField[]>([]);
  metadataLoading = signal(true);

  // Provider-asset metadata
  providerAssetFields = signal<AssetTypeProviderAssetMetadataField[]>([]);
  providerAssetMetadata = signal<Record<string, MetadataEntry[]>>({});

  // Provider selector
  selectedProviderId = signal<string | null>(null);
  providerLinkOptions = computed(() => {
    const asset = this.assetService.selectedAsset();
    if (!asset) return [];
    return asset.provider_links.map(link => ({
      label: link.provider_name ?? link.provider_id,
      value: link.provider_id,
    }));
  });
  selectedProviderLink = computed<ProviderAssetLink | null>(() => {
    const asset = this.assetService.selectedAsset();
    const pid = this.selectedProviderId();
    if (!asset || !pid) return null;
    return asset.provider_links.find(l => l.provider_id === pid) ?? null;
  });

  // History grid state
  historyGrid = signal<MetadataHistoryGrid | null>(null);
  historyLoading = signal(false);
  paHistoryGrids = signal<Record<string, MetadataHistoryGrid>>({});
  paHistoryLoading = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.assetId) return;
      this.assetId = id;
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.assetTypeFields.set([]);
      this.providerAssetFields.set([]);
      this.providerAssetMetadata.set({});
      this.historyGrid.set(null);
      this.paHistoryGrids.set({});

      // Restore tab from query params
      const tab = this.route.snapshot.queryParamMap.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Details');
      }

      this.metadataLoading.set(true);
      this.assetService.loadAssetDetail(this.assetId);
      this.assetService.loadAssetTypes();
      this.loadMetadata();
      this.loadAssetTypeFields();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });

    // Load history data when switching to History tab
    if (tab === 'History') {
      this.loadHistoryGrid();
      this.loadPAHistoryGrids();
    }
  }

  private loadAssetTypeFields(): void {
    const check = () => {
      const asset = this.assetService.selectedAsset();
      if (asset) {
        this.assetService.getAssetTypeMetadata(asset.asset_type_id).subscribe({
          next: fields => {
            this.assetTypeFields.set(fields);
            this.metadataLoading.set(false);
          },
          error: () => this.metadataLoading.set(false),
        });
        this.assetService.getAssetTypeProviderAssetMetadata(asset.asset_type_id).subscribe({
          next: fields => {
            this.providerAssetFields.set(fields);
            this.loadProviderAssetMetadata();
          },
        });
      } else {
        setTimeout(check, 100);
      }
    };
    check();
  }

  private loadProviderAssetMetadata(): void {
    const asset = this.assetService.selectedAsset();
    if (!asset) return;
    // Auto-select first provider if none selected
    if (!this.selectedProviderId() && asset.provider_links.length > 0) {
      this.selectedProviderId.set(asset.provider_links[0].provider_id);
    }
    const result: Record<string, MetadataEntry[]> = {};
    for (const link of asset.provider_links) {
      this.assetService.getProviderAssetMetadata(link.provider_id, this.assetId).subscribe({
        next: entries => {
          result[link.provider_id] = entries;
          this.providerAssetMetadata.set({ ...result });
        },
      });
    }
  }

  onProviderSelect(providerId: string): void {
    this.selectedProviderId.set(providerId);
  }

  getProviderAssetFieldValue(providerId: string, metadataId: string): any {
    const entries = this.providerAssetMetadata()[providerId] ?? [];
    const entry = entries.find(e => e.metadata_id === metadataId);
    return entry?.value ?? null;
  }

  paFieldTimestamp(providerId: string, metadataId: string): string | null {
    const entries = this.providerAssetMetadata()[providerId] ?? [];
    const entry = entries.find(e => e.metadata_id === metadataId);
    return entry?.timestamp ?? null;
  }

  // ---- Edit ----

  startEdit(): void {
    const asset = this.assetService.selectedAsset();
    if (!asset) return;
    this.editDisplayName = asset.display_name;
    this.editName = asset.name;
    this.editDescription = asset.description ?? '';
    this.editAssetTypeId = asset.asset_type_id;
    this.editIsActive = asset.is_active;
    this.editTimestamp = new Date();
    this.generalEditValues.set({
      name: this.editName,
      displayName: this.editDisplayName,
      type: this.editAssetTypeId,
      isActive: this.editIsActive,
      description: this.editDescription,
    });

    // Pre-populate metadata field values from current entries
    this.editFieldValues = {};
    for (const field of this.assetTypeFields()) {
      const entry = this.metadataEntries().find(e => e.metadata_id === field.metadata_id);
      if (entry) {
        this.editFieldValues[field.metadata_id] = typeof entry.value === 'object'
          ? JSON.stringify(entry.value)
          : String(entry.value);
      } else {
        this.editFieldValues[field.metadata_id] = '';
      }
    }
    this.metadataEditValues.set({ ...this.editFieldValues });

    // Pre-populate provider-asset metadata field values
    this.editPAFieldValues = {};
    for (const link of asset.provider_links) {
      for (const paf of this.providerAssetFields()) {
        const key = link.provider_id + ':' + paf.metadata_id;
        const val = this.getProviderAssetFieldValue(link.provider_id, paf.metadata_id);
        if (val !== null) {
          this.editPAFieldValues[key] = typeof val === 'object' ? JSON.stringify(val) : String(val);
        } else {
          this.editPAFieldValues[key] = '';
        }
      }
    }

    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'displayName') this.editDisplayName = e.value;
    else if (e.key === 'type') this.editAssetTypeId = e.value;
    else if (e.key === 'isActive') this.editIsActive = e.value;
    else if (e.key === 'description') this.editDescription = e.value;
  }

  onMetadataEditChange(e: { key: string; value: any }): void {
    this.editFieldValues[e.key] = String(e.value);
    this.metadataEditValues.update(v => ({ ...v, [e.key]: String(e.value) }));
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  submitEdit(): void {
    if (!this.editName.trim() || !this.editDisplayName.trim()) return;
    const asset = this.assetService.selectedAsset();
    if (!asset) return;

    const calls: any[] = [];

    // 1. Save base fields
    calls.push(this.assetService.updateAsset(this.assetId, {
      name: this.editName.trim(),
      display_name: this.editDisplayName.trim(),
      description: this.editDescription.trim() || null,
      is_active: this.editIsActive,
      asset_type_id: this.editAssetTypeId,
    }));

    // 2. Collect changed asset metadata fields
    const changedEntries: { metadata_id: string; value: any }[] = [];
    for (const field of this.assetTypeFields()) {
      const rawValue = this.editFieldValues[field.metadata_id] ?? '';
      const currentEntry = this.metadataEntries().find(e => e.metadata_id === field.metadata_id);
      const currentStr = currentEntry
        ? (typeof currentEntry.value === 'object' ? JSON.stringify(currentEntry.value) : String(currentEntry.value))
        : '';

      if (rawValue !== currentStr && rawValue !== '') {
        let value: any = rawValue;
        if (field.value_type === 'integer') {
          value = parseInt(rawValue, 10);
          if (isNaN(value)) continue;
        } else if (field.value_type === 'float') {
          value = parseFloat(rawValue);
          if (isNaN(value)) continue;
        } else if (field.value_type === 'boolean') {
          value = rawValue === 'true';
        }
        changedEntries.push({ metadata_id: field.metadata_id, value });
      }
    }

    if (changedEntries.length > 0) {
      calls.push(this.assetService.batchSaveAssetMetadata(this.assetId, {
        timestamp: this.editTimestamp.toISOString(),
        entries: changedEntries,
      }));
    }

    // 3. Collect changed provider-asset metadata fields (per provider link)
    for (const link of asset.provider_links) {
      const paChangedEntries: { metadata_id: string; value: any }[] = [];
      for (const paf of this.providerAssetFields()) {
        const key = link.provider_id + ':' + paf.metadata_id;
        const rawValue = this.editPAFieldValues[key] ?? '';
        const currentVal = this.getProviderAssetFieldValue(link.provider_id, paf.metadata_id);
        const currentStr = currentVal !== null
          ? (typeof currentVal === 'object' ? JSON.stringify(currentVal) : String(currentVal))
          : '';

        if (rawValue !== currentStr && rawValue !== '') {
          let value: any = rawValue;
          if (paf.value_type === 'integer') {
            value = parseInt(rawValue, 10);
            if (isNaN(value)) continue;
          } else if (paf.value_type === 'float') {
            value = parseFloat(rawValue);
            if (isNaN(value)) continue;
          } else if (paf.value_type === 'boolean') {
            value = rawValue === 'true';
          }
          paChangedEntries.push({ metadata_id: paf.metadata_id, value });
        }
      }

      if (paChangedEntries.length > 0) {
        calls.push(this.assetService.batchSaveProviderAssetMetadata(link.provider_id, this.assetId, {
          timestamp: this.editTimestamp.toISOString(),
          entries: paChangedEntries,
        }));
      }
    }

    forkJoin(calls).subscribe({
      next: () => {
        this.toast.success('Asset updated');
        this.editing.set(false);
        this.assetService.loadAssetDetail(this.assetId, true);
        this.loadMetadata();
        this.loadProviderAssetMetadata();
      },
      error: () => this.toast.error('Failed to update asset'),
    });
  }

  openDelete(): void {
    this.deleteUsage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getAssetUsage(this.assetId).subscribe({
      next: usage => this.deleteUsage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.assetService.deleteAsset(this.assetId).subscribe({
      next: () => {
        this.toast.success('Asset deleted');
        this.showDeleteDialog.set(false);
        window.history.back();
      },
      error: () => {
        this.toast.error('Failed to delete asset');
        this.deleting.set(false);
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

  fieldTimestamp(metadataId: string): string | null {
    const entry = this.metadataEntries().find(e => e.metadata_id === metadataId);
    return entry?.timestamp ?? null;
  }

  // ---- History Grid ----

  loadHistoryGrid(): void {
    this.historyLoading.set(true);
    this.assetService.getAssetMetadataHistoryGrid(this.assetId).subscribe({
      next: grid => {
        this.historyGrid.set(grid);
        this.historyLoading.set(false);
      },
      error: () => this.historyLoading.set(false),
    });
  }

  loadPAHistoryGrids(): void {
    const asset = this.assetService.selectedAsset();
    if (!asset || asset.provider_links.length === 0) return;
    this.paHistoryLoading.set(true);
    const result: Record<string, MetadataHistoryGrid> = {};
    let pending = asset.provider_links.length;
    for (const link of asset.provider_links) {
      this.assetService.getProviderAssetMetadataHistoryGrid(link.provider_id, this.assetId).subscribe({
        next: grid => {
          result[link.provider_id] = grid;
          this.paHistoryGrids.set({ ...result });
          if (--pending === 0) this.paHistoryLoading.set(false);
        },
        error: () => { if (--pending === 0) this.paHistoryLoading.set(false); },
      });
    }
  }

  onHistorySave(data: BulkHistoryUpdate): void {
    this.assetService.bulkUpdateAssetMetadataHistory(this.assetId, data).subscribe({
      next: () => {
        this.toast.success('History updated');
        this.loadHistoryGrid();
        this.loadMetadata();
        this.assetService.loadAssetDetail(this.assetId, true);
      },
      error: () => this.toast.error('Failed to update history'),
    });
  }

  onPAHistorySave(providerId: string, data: BulkHistoryUpdate): void {
    this.assetService.bulkUpdateProviderAssetMetadataHistory(providerId, this.assetId, data).subscribe({
      next: () => {
        this.toast.success('Provider mapping history updated');
        this.loadPAHistoryGrids();
        this.loadProviderAssetMetadata();
        this.assetService.loadAssetDetail(this.assetId, true);
      },
      error: () => this.toast.error('Failed to update provider mapping history'),
    });
  }

  // ---- Helpers ----

  formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
}
