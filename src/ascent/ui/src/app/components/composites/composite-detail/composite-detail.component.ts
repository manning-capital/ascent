import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { CompositeService } from '../../../services/composite.service';
import { AssetService } from '../../../services/asset.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import {
  Composite, CompositeMemberCreate, CompositeTypeItem,
  CompositeTypeMetadataField,
} from '../../../models/composite.model';
import {
  MetadataEntry, MetadataHistoryGrid, BulkHistoryUpdate,
} from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Skeleton } from 'primeng/skeleton';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Button } from 'primeng/button';
import { Panel } from 'primeng/panel';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-composite-detail',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    Tabs, TabList, Tab,
    Select,
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
  templateUrl: './composite-detail.component.html',
})
export class CompositeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  compositeService = inject(CompositeService);
  assetService = inject(AssetService);
  private fieldService = inject(FieldService);

  tabs = ['Details', 'History', 'Settings'];
  activeTab = signal('Details');

  compositeId = '';
  composite = signal<Composite | null>(null);
  compositeType = signal<CompositeTypeItem | null>(null);
  loading = signal(false);

  // Metadata fields from type + actual values
  typeFields = signal<CompositeTypeMetadataField[]>([]);
  metadataEntries = signal<MetadataEntry[]>([]);
  metadataLoading = signal(true);

  // General panel fields
  generalFields = computed<PanelField[]>(() => {
    const comp = this.composite();
    const cType = this.compositeType();
    if (!comp) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: comp.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: comp.display_name },
      { type: 'link', key: 'type', label: 'Type', value: cType?.display_name ?? cType?.name ?? null, route: cType ? ['/settings/composite-types', cType.id] : [], fallback: 'Unknown',
        options: this.compositeService.compositeTypes().map(t => ({ label: t.display_name || t.name, value: t.id })) },
      { type: 'text', key: 'members', label: 'Members', value: comp.members.length },
      { type: 'active', key: 'isActive', label: 'Active', value: comp.is_active },
      { type: 'date', key: 'createdAt', label: 'Created', value: comp.created_at },
      { type: 'text', key: 'description', label: 'Description', value: comp.description },
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
  editCompositeTypeId = '';
  editIsActive = true;
  editTimestamp: Date = new Date();
  editFieldValues: Record<string, string> = {};

  // Add member form
  showMemberForm = signal(false);
  newInstrumentId = '';

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
      if (id === this.compositeId) return;
      this.compositeId = id;

      const tab = this.route.snapshot.queryParamMap.get('tab');
      this.activeTab.set(tab && this.tabs.includes(tab) ? tab : 'Details');
      this.showMemberForm.set(false);
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.typeFields.set([]);
      this.historyGrid.set(null);

      this.metadataLoading.set(true);
      this.loadComposite();
      this.loadMetadata();
      this.assetService.loadInstruments();
      this.compositeService.loadCompositeTypes();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
    if (tab === 'History') {
      this.loadHistoryGrid();
    }
  }

  loadComposite(): void {
    this.loading.set(true);
    this.compositeService.getCompositeDetail(this.compositeId).subscribe({
      next: composite => {
        this.composite.set(composite);
        this.loading.set(false);
        this.loadTypeInfo(composite.composite_type_id);
      },
      error: () => this.loading.set(false),
    });
  }

  private loadTypeInfo(typeId: string): void {
    const check = () => {
      const types = this.compositeService.compositeTypes();
      const found = types.find(t => t.id === typeId);
      if (found) {
        this.compositeType.set(found);
      } else if (types.length === 0) {
        setTimeout(check, 100);
      }
    };
    check();

    this.compositeService.getCompositeTypeMetadata(typeId).subscribe({
      next: fields => {
        this.typeFields.set(fields);
        this.metadataLoading.set(false);
      },
      error: () => this.metadataLoading.set(false),
    });
  }

  loadMetadata(): void {
    this.compositeService.getCompositeMetadata(this.compositeId).subscribe({
      next: entries => this.metadataEntries.set(entries),
    });
  }

  getTypeName(): string {
    return this.compositeType()?.display_name ?? this.compositeType()?.name ?? 'Unknown';
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
    const comp = this.composite();
    if (!comp) return;
    this.editCompositeTypeId = comp.composite_type_id;
    this.editIsActive = comp.is_active;
    this.editTimestamp = new Date();
    this.generalEditValues.set({
      type: this.editCompositeTypeId,
      isActive: this.editIsActive,
    });

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
    this.metadataEditValues.set({ ...this.editFieldValues });

    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'type') this.editCompositeTypeId = e.value;
    else if (e.key === 'isActive') this.editIsActive = e.value;
  }

  onMetadataEditChange(e: { key: string; value: any }): void {
    this.editFieldValues[e.key] = String(e.value);
    this.metadataEditValues.update(v => ({ ...v, [e.key]: String(e.value) }));
  }

  submitEdit(): void {
    const comp = this.composite();
    if (!comp) return;

    const calls: any[] = [];

    calls.push(this.compositeService.updateComposite(this.compositeId, {
      is_active: this.editIsActive,
      composite_type_id: this.editCompositeTypeId,
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
      calls.push(this.compositeService.batchSaveCompositeMetadata(this.compositeId, {
        timestamp: this.editTimestamp.toISOString(),
        entries: changedEntries,
      }));
    }

    forkJoin(calls).subscribe({
      next: () => {
        this.toast.success('Composite updated');
        this.editing.set(false);
        this.loadComposite();
        this.loadMetadata();
      },
      error: () => this.toast.error('Failed to update composite'),
    });
  }

  // ---- Members ----

  openMemberForm(): void {
    this.newInstrumentId = this.assetService.instruments()[0]?.id ?? '';
    this.showMemberForm.set(true);
  }

  cancelMemberForm(): void {
    this.showMemberForm.set(false);
  }

  submitMember(): void {
    if (!this.newInstrumentId) return;
    const comp = this.composite();
    const data: CompositeMemberCreate = {
      instrument_id: this.newInstrumentId,
      order: (comp?.members.length ?? 0) + 1,
    };
    this.compositeService.addCompositeMember(this.compositeId, data).subscribe({
      next: () => {
        this.toast.success('Member added');
        this.showMemberForm.set(false);
        this.loadComposite();
      },
      error: () => this.toast.error('Failed to add member'),
    });
  }

  removeMember(m: any): void {
    this.compositeService.removeCompositeMember(this.compositeId, m.instrument_id).subscribe({
      next: () => {
        this.toast.success('Member removed');
        this.loadComposite();
      },
      error: () => this.toast.error('Failed to remove member'),
    });
  }

  // ---- History ----

  loadHistoryGrid(): void {
    this.historyLoading.set(true);
    this.compositeService.getCompositeMetadataHistoryGrid(this.compositeId).subscribe({
      next: grid => {
        this.historyGrid.set(grid);
        this.historyLoading.set(false);
      },
      error: () => this.historyLoading.set(false),
    });
  }

  onHistorySave(data: BulkHistoryUpdate): void {
    this.compositeService.bulkUpdateCompositeMetadataHistory(this.compositeId, data).subscribe({
      next: () => {
        this.toast.success('History updated');
        this.loadHistoryGrid();
        this.loadMetadata();
        this.loadComposite();
      },
      error: () => this.toast.error('Failed to update history'),
    });
  }

  // ---- Delete ----

  openDelete(): void {
    this.deleteUsage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getCompositeUsage(this.compositeId).subscribe({
      next: usage => this.deleteUsage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.compositeService.deleteComposite(this.compositeId).subscribe({
      next: () => {
        this.toast.success('Composite deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/composites']);
      },
      error: () => {
        this.toast.error('Failed to delete composite');
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
