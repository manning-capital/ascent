import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import {
  Instrument, InstrumentTypeItem,
  InstrumentTypeMetadataField, MetadataEntry, MetadataHistoryGrid, BulkHistoryUpdate,
} from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Skeleton } from 'primeng/skeleton';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Button } from 'primeng/button';
import { Panel } from 'primeng/panel';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-instrument-detail',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    Tabs, TabList, Tab,
    DatePicker,
    TableModule,
    Tag,
    Button,
    Skeleton,
    Panel,
    MetadataHistoryTableComponent,
    SafeDeleteDialogComponent,
    FieldPanelComponent,
  ],
  templateUrl: './instrument-detail.component.html',
})
export class InstrumentDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private fieldService = inject(FieldService);

  tabs = ['Details', 'History', 'Settings'];
  activeTab = signal('Details');

  instrumentId = '';
  instrument = signal<Instrument | null>(null);
  instrumentType = signal<InstrumentTypeItem | null>(null);
  loading = signal(false);

  // Metadata fields from type + actual values
  typeFields = signal<InstrumentTypeMetadataField[]>([]);
  metadataEntries = signal<MetadataEntry[]>([]);
  metadataLoading = signal(true);

  // Resolved entity lookups
  instrumentProvider = computed(() => {
    const inst = this.instrument();
    if (!inst) return null;
    return this.providerService.providers().find(p => p.id === inst.provider_id) ?? null;
  });
  fromAsset = computed(() => {
    const inst = this.instrument();
    if (!inst) return null;
    return this.assetService.assets().find(a => a.id === inst.from_asset_id) ?? null;
  });
  toAsset = computed(() => {
    const inst = this.instrument();
    if (!inst) return null;
    return this.assetService.assets().find(a => a.id === inst.to_asset_id) ?? null;
  });

  // General panel fields
  generalFields = computed<PanelField[]>(() => {
    const inst = this.instrument();
    const iType = this.instrumentType();
    const prov = this.instrumentProvider();
    const fAsset = this.fromAsset();
    const tAsset = this.toAsset();
    if (!inst) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: inst.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: inst.display_name },
      { type: 'link', key: 'type', label: 'Type', value: iType?.display_name ?? iType?.name ?? null, route: iType ? ['/settings/instrument-types', iType.id] : [], fallback: 'Unknown',
        options: this.assetService.instrumentTypes().map(t => ({ label: t.display_name || t.name, value: t.id })) },
      { type: 'link', key: 'provider', label: 'Provider', value: prov?.display_name ?? prov?.name ?? inst.provider_name, route: prov ? ['/settings/providers', prov.id] : [], fallback: '-',
        options: this.providerService.providers().map(p => ({ label: p.display_name || p.name, value: p.id })) },
      { type: 'link', key: 'fromAsset', label: 'From Asset', value: fAsset?.display_name ?? fAsset?.name ?? inst.from_asset_name, route: fAsset ? ['/settings/assets', fAsset.id] : [], fallback: '-',
        options: this.assetService.assets().map(a => ({ label: a.display_name || a.name, value: a.id })) },
      { type: 'link', key: 'toAsset', label: 'To Asset', value: tAsset?.display_name ?? tAsset?.name ?? inst.to_asset_name, route: tAsset ? ['/settings/assets', tAsset.id] : [], fallback: '-',
        options: this.assetService.assets().map(a => ({ label: a.display_name || a.name, value: a.id })) },
      { type: 'active', key: 'isActive', label: 'Active', value: inst.is_active },
      { type: 'date', key: 'createdAt', label: 'Created', value: inst.created_at },
      { type: 'text', key: 'description', label: 'Description', value: inst.description },
    ];
  });
  generalEditValues = signal<Record<string, any>>({});

  // Metadata panel fields
  metadataFields = computed<PanelField[]>(() => {
    const fields = this.typeFields();
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
        case 'enum': return { ...base, type: 'tag' as const, value: val != null ? String(val) : '', severity: 'secondary', options: (field.config?.['options'] as string[] ?? []).map((o: string) => ({ label: o, value: o })) };
        case 'reference': {
          const refOpts = this.getReferenceOptions(field.config?.['ref_table'] ?? null);
          const refItem = refOpts.find(o => o.value === val);
          const refRoute = val ? this.getReferenceRoute(field.config?.['ref_table'] ?? null, String(val)) : [];
          return { ...base, type: 'link' as const, value: refItem?.label ?? (val ? String(val) : null), route: refRoute, fallback: 'Not set', options: refOpts };
        }
        default: return { ...base, type: 'text' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
      }
    });
  });
  metadataEditValues = signal<Record<string, any>>({});
  private getReferenceOptions(refTable: string | null): { label: string; value: string }[] {
    if (!refTable) return [];
    switch (refTable) {
      case 'asset': return (this as any).assetService?.assets()?.map((a: any) => ({ label: a.display_name || a.name, value: a.id })) ?? [];
      case 'instrument': return (this as any).assetService?.instruments()?.map((i: any) => ({ label: i.display_name || i.name, value: i.id })) ?? [];
      case 'composite': return (this as any).compositeService?.composites()?.map((c: any) => ({ label: c.display_name || c.name, value: c.id })) ?? [];
      case 'provider': return (this as any).providerService?.providers()?.map((p: any) => ({ label: p.display_name || p.name, value: p.id })) ?? [];
      default: return [];
    }
  }

  private getReferenceRoute(refTable: string | null, id: string): string[] {
    switch (refTable) {
      case 'asset': return ['/settings/assets', id];
      case 'instrument': return ['/settings/instruments', id];
      case 'composite': return ['/settings/composites', id];
      case 'provider': return ['/settings/providers', id];
      default: return [];
    }
  }

  // Edit state
  editing = signal(false);
  editInstrumentTypeId = '';
  editProviderId = '';
  editFromAssetId = '';
  editToAssetId = '';
  editIsActive = true;
  editTimestamp: Date = new Date();
  editFieldValues: Record<string, string> = {};

  // Delete
  showDeleteDialog = signal(false);
  deleteUsage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  // History grid
  historyGrid = signal<MetadataHistoryGrid | null>(null);
  historyRefOptions = computed(() => {
    const grid = this.historyGrid();
    if (!grid) return {};
    const opts: Record<string, { label: string; value: string }[]> = {};
    for (const f of grid.fields) {
      if (f.value_type === 'reference' && f.config?.['ref_table']) {
        opts[f.metadata_id] = this.getReferenceOptions(f.config['ref_table']);
      }
    }
    return opts;
  });
  historyLoading = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.instrumentId) return;
      this.instrumentId = id;

      const tab = this.route.snapshot.queryParamMap.get('tab');
      this.activeTab.set(tab && this.tabs.includes(tab) ? tab : 'Details');
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.typeFields.set([]);
      this.historyGrid.set(null);

      this.metadataLoading.set(true);
      this.loadInstrument();
      this.loadMetadata();
      this.assetService.loadAssets();
      this.assetService.loadInstrumentTypes();
      this.providerService.loadProviders();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
    if (tab === 'History') {
      this.loadHistoryGrid();
    }
  }

  loadInstrument(): void {
    this.loading.set(true);
    this.assetService.getInstrumentDetail(this.instrumentId).subscribe({
      next: instrument => {
        this.instrument.set(instrument);
        this.loading.set(false);
        this.loadTypeInfo(instrument.instrument_type_id);
      },
      error: () => this.loading.set(false),
    });
  }

  private loadTypeInfo(typeId: string): void {
    const check = () => {
      const types = this.assetService.instrumentTypes();
      const found = types.find(t => t.id === typeId);
      if (found) {
        this.instrumentType.set(found);
      } else if (types.length === 0) {
        setTimeout(check, 100);
      }
    };
    check();

    this.assetService.getInstrumentTypeMetadata(typeId).subscribe({
      next: fields => {
        this.typeFields.set(fields);
        this.metadataLoading.set(false);
      },
      error: () => this.metadataLoading.set(false),
    });
  }

  loadMetadata(): void {
    this.assetService.getInstrumentMetadata(this.instrumentId).subscribe({
      next: entries => this.metadataEntries.set(entries),
    });
  }

  getTypeName(): string {
    return this.instrumentType()?.display_name ?? this.instrumentType()?.name ?? 'Unknown';
  }

  fieldValue(metadataId: string): any {
    const entry = this.metadataEntries().find(e => e.metadata_id === metadataId);
    return entry?.value ?? null;
  }

  fieldTimestamp(metadataId: string): string | null {
    const entry = this.metadataEntries().find(e => e.metadata_id === metadataId);
    return entry?.timestamp ?? null;
  }

  formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  // ---- Edit ----

  startEdit(): void {
    const inst = this.instrument();
    if (!inst) return;
    this.editInstrumentTypeId = inst.instrument_type_id;
    this.editProviderId = inst.provider_id;
    this.editFromAssetId = inst.from_asset_id;
    this.editToAssetId = inst.to_asset_id;
    this.editIsActive = inst.is_active;
    this.editTimestamp = new Date();

    this.editFieldValues = {};
    for (const field of this.typeFields()) {
      const entry = this.metadataEntries().find(e => e.metadata_id === field.metadata_id);
      if (entry) {
        this.editFieldValues[field.metadata_id] = typeof entry.value === 'object'
          ? JSON.stringify(entry.value)
          : String(entry.value);
      } else {
        this.editFieldValues[field.metadata_id] = '';
      }
    }

    this.generalEditValues.set({
      type: this.editInstrumentTypeId,
      provider: this.editProviderId,
      fromAsset: this.editFromAssetId,
      toAsset: this.editToAssetId,
      isActive: this.editIsActive,
    });
    this.metadataEditValues.set({ ...this.editFieldValues });

    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'type') this.editInstrumentTypeId = e.value;
    else if (e.key === 'provider') this.editProviderId = e.value;
    else if (e.key === 'fromAsset') this.editFromAssetId = e.value;
    else if (e.key === 'toAsset') this.editToAssetId = e.value;
    else if (e.key === 'isActive') this.editIsActive = e.value;
  }

  onMetadataEditChange(e: { key: string; value: any }): void {
    this.editFieldValues[e.key] = String(e.value);
    this.metadataEditValues.update(v => ({ ...v, [e.key]: String(e.value) }));
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  submitEdit(): void {
    const inst = this.instrument();
    if (!inst) return;

    const calls: any[] = [];

    calls.push(this.assetService.updateInstrument(this.instrumentId, {
      is_active: this.editIsActive,
      instrument_type_id: this.editInstrumentTypeId,
      provider_id: this.editProviderId,
      from_asset_id: this.editFromAssetId,
      to_asset_id: this.editToAssetId,
    }));

    const changedEntries: { metadata_id: string; value: any }[] = [];
    for (const field of this.typeFields()) {
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
      calls.push(this.assetService.batchSaveInstrumentMetadata(this.instrumentId, {
        timestamp: this.editTimestamp.toISOString(),
        entries: changedEntries,
      }));
    }

    forkJoin(calls).subscribe({
      next: () => {
        this.toast.success('Instrument updated');
        this.editing.set(false);
        this.loadInstrument();
        this.loadMetadata();
      },
      error: () => this.toast.error('Failed to update instrument'),
    });
  }

  // ---- History ----

  loadHistoryGrid(): void {
    this.historyLoading.set(true);
    this.assetService.getInstrumentMetadataHistoryGrid(this.instrumentId).subscribe({
      next: grid => {
        this.historyGrid.set(grid);
        this.historyLoading.set(false);
      },
      error: () => this.historyLoading.set(false),
    });
  }

  onHistorySave(data: BulkHistoryUpdate): void {
    this.assetService.bulkUpdateInstrumentMetadataHistory(this.instrumentId, data).subscribe({
      next: () => {
        this.toast.success('History updated');
        this.loadHistoryGrid();
        this.loadMetadata();
        this.loadInstrument();
      },
      error: () => this.toast.error('Failed to update history'),
    });
  }

  // ---- Delete ----

  openDelete(): void {
    this.deleteUsage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getInstrumentUsage(this.instrumentId).subscribe({
      next: usage => this.deleteUsage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.assetService.deleteInstrument(this.instrumentId).subscribe({
      next: () => {
        this.toast.success('Instrument deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/instruments']);
      },
      error: () => {
        this.toast.error('Failed to delete instrument');
        this.deleting.set(false);
      },
    });
  }

  // ---- Helpers ----

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime' };
    return labels[vt] ?? vt;
  }
}
