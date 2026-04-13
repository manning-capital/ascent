import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { forkJoin, Observable } from 'rxjs';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { CompositeService } from '../../../services/composite.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, ProviderTypeMetadataField, MetadataHistoryGrid, BulkHistoryUpdate } from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Skeleton } from 'primeng/skeleton';
import { DatePicker } from 'primeng/datepicker';
import { Tag } from 'primeng/tag';
import { Panel } from 'primeng/panel';
import { Button } from 'primeng/button';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import type { DataTableColumn } from '../../shared/data-table/data-table.model';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-provider-detail',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    DatePicker,
    Tag,
    Panel,
    Button,
    Skeleton,
    Tabs, TabList, Tab,
    DataTableComponent,
    MetadataHistoryTableComponent,
    SafeDeleteDialogComponent,
    FieldPanelComponent,
  ],
  templateUrl: './provider-detail.component.html',
})
export class ProviderDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private compositeService = inject(CompositeService);
  private fieldService = inject(FieldService);

  providerId = '';

  // Type lookup
  providerType = computed(() => {
    const provider = this.providerService.selectedProvider();
    if (!provider) return null;
    return this.providerService.providerTypes().find(t => t.id === provider.provider_type_id) ?? null;
  });

  // Mapped assets table columns
  mappedAssetsColumns: DataTableColumn[] = [
    { field: 'asset_name', header: 'Asset', cellType: 'link', linkRoute: (row: any) => ['/settings/assets', row.asset_id] },
    { field: 'asset_symbol', header: 'Symbol', cellType: 'monospace', valueGetter: (params: any) => params.data?.asset_symbol || '-' },
    { field: 'identifier', header: 'Identifier', cellType: 'monospace' },
    { field: 'created_at', header: 'Created', cellType: 'date' },
  ];

  // General panel fields
  generalFields = computed<PanelField[]>(() => {
    const provider = this.providerService.selectedProvider();
    const pType = this.providerType();
    if (!provider) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: provider.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: provider.display_name },
      { type: 'link', key: 'type', label: 'Type', value: pType?.display_name ?? pType?.name ?? null, route: pType ? ['/settings/provider-types', pType.id] : [], fallback: '-',
        options: this.providerService.providerTypes().map(t => ({ label: t.display_name || t.name, value: t.id })) },
      { type: 'mono', key: 'externalCode', label: 'External Code', value: provider.provider_external_code, fallback: '-' },
      { type: 'external-link', key: 'url', label: 'URL', value: provider.url, href: provider.url, fallback: '-' },
      { type: 'active', key: 'isActive', label: 'Active', value: provider.is_active },
      { type: 'date', key: 'createdAt', label: 'Created', value: provider.created_at },
      { type: 'text', key: 'description', label: 'Description', value: provider.description },
    ];
  });
  generalEditValues = signal<Record<string, any>>({});

  // Metadata panel fields
  metadataFields = computed<PanelField[]>(() => {
    const fields = this.providerTypeFields();
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
        case 'date': return { ...base, type: 'date' as const, value: val != null ? String(val) : null };
        case 'time': return { ...base, type: 'time' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
        case 'datetime': return { ...base, type: 'datetime' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
        case 'enum': return { ...base, type: 'tag' as const, value: val != null ? String(val) : '', severity: 'secondary', options: (field.config?.['options'] as string[] ?? []).map((o: string) => ({ label: o, value: o })) };
        case 'reference': {
          const refTable = field.config?.['ref_table'] ?? null;
          const refOpts = this.getReferenceOptions(refTable);
          const refItem = refOpts.find(o => o.value === val);
          const refRoute = val ? this.getReferenceRoute(refTable, String(val)) : [];
          return { ...base, type: 'link' as const, value: refItem?.label ?? (val ? String(val) : null), route: refRoute, fallback: 'Not set', searchFn: this.getReferenceSearchFn(refTable) };
        }
        default: return { ...base, type: 'text' as const, value: val != null ? String(val) : null, fallback: 'Not set' };
      }
    });
  });
  metadataEditValues = signal<Record<string, any>>({});
  private getReferenceOptions(refTable: string | null): { label: string; value: string }[] {
    if (!refTable) return [];
    switch (refTable) {
      case 'asset': return this.assetService.assets().map(a => ({ label: a.display_name || a.name, value: a.id }));
      case 'instrument': return this.assetService.instruments().map(i => ({ label: i.display_name || i.name, value: i.id }));
      case 'composite': return this.compositeService.composites().map(c => ({ label: c.display_name || c.name, value: c.id }));
      case 'provider': return this.providerService.providers().map(p => ({ label: p.display_name || p.name, value: p.id }));
      default: return [];
    }
  }

  private getReferenceSearchFn(refTable: string | null): ((query: string) => Observable<{ label: string; value: string }[]>) | undefined {
    if (!refTable) return undefined;
    switch (refTable) {
      case 'asset': return (q: string) => this.assetService.searchAssets(q);
      case 'instrument': return (q: string) => this.assetService.searchInstruments(q);
      case 'composite': return (q: string) => this.compositeService.searchComposites(q);
      case 'provider': return (q: string) => this.providerService.searchProviders(q);
      default: return undefined;
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

  // Tabs
  tabs = ['Details', 'History', 'Settings'];
  private _initTab = this.route.snapshot.queryParamMap.get('tab');
  activeTab = signal(this._initTab && this.tabs.includes(this._initTab) ? this._initTab : 'Details');

  // Delete
  showDeleteDialog = signal(false);
  deleteUsage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  // Edit state
  editing = signal(false);
  editName = '';
  editDisplayName = '';
  editDescription = '';
  editProviderTypeId = '';
  editExternalCode = '';
  editUrl = '';
  editIsActive = true;
  editTimestamp: Date = new Date();
  editFieldValues: Record<string, string> = {};

  // Metadata state
  metadataEntries = signal<MetadataEntry[]>([]);
  providerTypeFields = signal<ProviderTypeMetadataField[]>([]);
  metadataLoading = signal(true);

  // History grid state
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
      if (id === this.providerId) return;
      this.providerId = id;
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.providerTypeFields.set([]);
      this.metadataLoading.set(true);
      this.historyGrid.set(null);

      // Restore tab from query params
      const tab = this.route.snapshot.queryParamMap.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Details');
      }

      this.providerService.loadProviderDetail(this.providerId);
      this.providerService.loadProviderTypes();
      this.providerService.loadProviders();
      this.assetService.loadAssets();
      this.assetService.loadInstruments();
      this.loadMetadata();
      this.loadProviderTypeFields();

      if (this.activeTab() === 'History') {
        this.loadHistoryGrid();
      }
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

    if (tab === 'History') {
      this.loadHistoryGrid();
    }
  }

  private loadProviderTypeFields(): void {
    const check = () => {
      const provider = this.providerService.selectedProvider();
      if (provider) {
        this.providerService.getProviderTypeMetadata(provider.provider_type_id).subscribe({
          next: fields => {
            this.providerTypeFields.set(fields);
            this.metadataLoading.set(false);
          },
          error: () => this.metadataLoading.set(false),
        });
      } else {
        setTimeout(check, 100);
      }
    };
    check();
  }

  // ---- Edit ----

  startEdit(): void {
    const provider = this.providerService.selectedProvider();
    if (!provider) return;
    this.editName = provider.name;
    this.editDisplayName = provider.display_name;
    this.editDescription = provider.description ?? '';
    this.editProviderTypeId = provider.provider_type_id;
    this.editExternalCode = provider.provider_external_code ?? '';
    this.editUrl = provider.url ?? '';
    this.editIsActive = provider.is_active;
    this.editTimestamp = new Date();

    this.generalEditValues.set({
      name: this.editName,
      displayName: this.editDisplayName,
      type: this.editProviderTypeId,
      externalCode: this.editExternalCode,
      url: this.editUrl,
      isActive: this.editIsActive,
      description: this.editDescription,
    });

    this.editFieldValues = {};
    for (const field of this.providerTypeFields()) {
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

    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'displayName') this.editDisplayName = e.value;
    else if (e.key === 'type') this.editProviderTypeId = e.value;
    else if (e.key === 'externalCode') this.editExternalCode = e.value;
    else if (e.key === 'url') this.editUrl = e.value;
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
    if (!this.editName.trim()) return;

    const baseUpdate = this.providerService.updateProvider(this.providerId, {
      name: this.editName.trim(),
      display_name: this.editDisplayName.trim(),
      description: this.editDescription.trim() || null,
      provider_type_id: this.editProviderTypeId,
      provider_external_code: this.editExternalCode.trim() || null,
      url: this.editUrl.trim() || null,
      is_active: this.editIsActive,
    });

    const changedEntries: { metadata_id: string; value: any }[] = [];
    for (const field of this.providerTypeFields()) {
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
      const batchSave = this.providerService.batchSaveProviderMetadata(this.providerId, {
        timestamp: this.editTimestamp.toISOString(),
        entries: changedEntries,
      });

      forkJoin([baseUpdate, batchSave]).subscribe({
        next: () => {
          this.toast.success('Provider updated');
          this.editing.set(false);
          this.providerService.loadProviderDetail(this.providerId, true);
          this.loadMetadata();
        },
        error: () => this.toast.error('Failed to update provider'),
      });
    } else {
      baseUpdate.subscribe({
        next: () => {
          this.toast.success('Provider updated');
          this.editing.set(false);
          this.providerService.loadProviderDetail(this.providerId, true);
        },
        error: () => this.toast.error('Failed to update provider'),
      });
    }
  }

  openDelete(): void {
    this.deleteUsage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getProviderUsage(this.providerId).subscribe({
      next: usage => this.deleteUsage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.providerService.deleteProvider(this.providerId).subscribe({
      next: () => {
        this.toast.success('Provider deleted');
        this.showDeleteDialog.set(false);
        window.history.back();
      },
      error: () => {
        this.toast.error('Failed to delete provider');
        this.deleting.set(false);
      },
    });
  }

  // ---- Metadata ----

  loadMetadata(): void {
    this.providerService.getProviderMetadata(this.providerId).subscribe({
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
    this.providerService.getProviderMetadataHistoryGrid(this.providerId).subscribe({
      next: grid => {
        this.historyGrid.set(grid);
        this.historyLoading.set(false);
      },
      error: () => this.historyLoading.set(false),
    });
  }

  onHistorySave(data: BulkHistoryUpdate): void {
    this.providerService.bulkUpdateProviderMetadataHistory(this.providerId, data).subscribe({
      next: () => {
        this.toast.success('History updated');
        this.loadHistoryGrid();
        this.loadMetadata();
        this.providerService.loadProviderDetail(this.providerId, true);
      },
      error: () => this.toast.error('Failed to update history'),
    });
  }

  // ---- Helpers ----

  formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
}
