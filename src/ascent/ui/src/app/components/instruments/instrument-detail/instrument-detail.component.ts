import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
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
import { Select } from 'primeng/select';
import { Checkbox } from 'primeng/checkbox';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Panel } from 'primeng/panel';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';

@Component({
  selector: 'app-instrument-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    Tabs, TabList, Tab,
    Select,
    Checkbox,
    DatePicker,
    TableModule,
    Tag,
    Button,
    InputText,
    Skeleton,
    Panel,
    MetadataHistoryTableComponent,
    SafeDeleteDialogComponent,
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

  // Edit state
  editing = signal(false);
  editIsActive = true;
  editTimestamp: Date = new Date();
  editFieldValues: Record<string, string> = {};

  // Delete
  showDeleteDialog = signal(false);
  deleteUsage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  // History grid
  historyGrid = signal<MetadataHistoryGrid | null>(null);
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

    this.editing.set(true);
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
