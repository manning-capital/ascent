import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ProviderService } from '../../../services/provider.service';
import { AssetService } from '../../../services/asset.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, MetadataHistoryEntry, ProviderTypeMetadataField } from '../../../models/asset.model';
import { LoadingSpinnerComponent } from '../../shared/loading-spinner.component';
import { PanelTabsComponent } from '../../shared/panel-tabs.component';

@Component({
  selector: 'app-provider-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    LoadingSpinnerComponent,
    PanelTabsComponent,
  ],
  templateUrl: './provider-detail.component.html',
})
export class ProviderDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private toast = inject(ToastService);
  providerService = inject(ProviderService);
  assetService = inject(AssetService);

  tabs = ['Overview', 'Metadata', 'Assets'];
  activeTab = signal('Overview');

  providerId = '';

  // Edit state
  editing = signal(false);
  editName = '';
  editDescription = '';
  editExternalCode = '';
  editUrl = '';
  editIsActive = true;

  // Metadata state
  metadataEntries = signal<MetadataEntry[]>([]);
  providerTypeFields = signal<ProviderTypeMetadataField[]>([]);
  fieldInputValues: Record<string, string> = {};
  fieldTimestampValues: Record<string, string> = {};
  showMetadataForm = signal(false);
  newMetadataId = '';
  newMetadataValue = '';
  newMetadataTimestamp = '';

  // History state
  historyMetadataId = signal<string | null>(null);
  historyMetadataName = signal('');
  historyEntries = signal<MetadataHistoryEntry[]>([]);
  editingHistoryTimestamp = signal<string | null>(null);
  editHistoryValue = '';
  editHistoryTimestamp = '';

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.providerId) return;
      this.providerId = id;

      this.activeTab.set('Overview');
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.providerTypeFields.set([]);
      this.fieldInputValues = {};
      this.fieldTimestampValues = {};
      this.showMetadataForm.set(false);
      this.historyMetadataId.set(null);
      this.historyEntries.set([]);

      this.providerService.loadProviderDetail(this.providerId);
      this.assetService.loadMetadataTypes();
      this.loadMetadata();
      this.loadProviderTypeFields();
    });
  }

  private loadProviderTypeFields(): void {
    const check = () => {
      const provider = this.providerService.selectedProvider();
      if (provider) {
        this.providerService.getProviderTypeMetadata(provider.provider_type_id).subscribe({
          next: fields => this.providerTypeFields.set(fields),
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
    this.editDescription = provider.description ?? '';
    this.editExternalCode = provider.provider_external_code ?? '';
    this.editUrl = provider.url ?? '';
    this.editIsActive = provider.is_active;
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  submitEdit(): void {
    if (!this.editName.trim()) return;
    this.providerService.updateProvider(this.providerId, {
      name: this.editName.trim(),
      description: this.editDescription.trim() || null,
      provider_external_code: this.editExternalCode.trim() || null,
      url: this.editUrl.trim() || null,
      is_active: this.editIsActive,
    }).subscribe({
      next: () => {
        this.toast.success('Provider updated');
        this.editing.set(false);
        this.providerService.loadProviderDetail(this.providerId, true);
      },
      error: () => this.toast.error('Failed to update provider'),
    });
  }

  deleteProvider(): void {
    this.providerService.deleteProvider(this.providerId).subscribe({
      next: () => {
        this.toast.success('Provider deleted');
        window.history.back();
      },
      error: () => this.toast.error('Failed to delete provider'),
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

  extraMetadata(): MetadataEntry[] {
    const fieldIds = new Set(this.providerTypeFields().map(f => f.metadata_id));
    return this.metadataEntries().filter(e => !fieldIds.has(e.metadata_id));
  }

  openMetadataForm(): void {
    const usedIds = new Set([
      ...this.providerTypeFields().map(f => f.metadata_id),
      ...this.metadataEntries().map(e => e.metadata_id),
    ]);
    const available = this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id));
    this.newMetadataId = available[0]?.id ?? this.assetService.metadataTypes()[0]?.id ?? '';
    this.newMetadataValue = '';
    this.newMetadataTimestamp = '';
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
      payload.timestamp = new Date(this.newMetadataTimestamp).toISOString();
    }
    this.providerService.addProviderMetadata(this.providerId, payload).subscribe({
      next: () => {
        this.toast.success('Metadata added');
        this.showMetadataForm.set(false);
        this.loadMetadata();
        this.providerService.loadProviderDetail(this.providerId, true);
      },
      error: () => this.toast.error('Failed to add metadata'),
    });
  }

  submitFieldValue(field: ProviderTypeMetadataField): void {
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
      payload.timestamp = new Date(ts).toISOString();
    }
    this.providerService.addProviderMetadata(this.providerId, payload).subscribe({
      next: () => {
        this.toast.success(`${field.metadata_name} updated`);
        this.fieldInputValues[field.metadata_id] = '';
        this.fieldTimestampValues[field.metadata_id] = '';
        this.loadMetadata();
        this.providerService.loadProviderDetail(this.providerId, true);
        if (this.historyMetadataId() === field.metadata_id) {
          this.refreshHistory();
        }
      },
      error: () => this.toast.error(`Failed to update ${field.metadata_name}`),
    });
  }

  deleteMetadata(entry: MetadataEntry): void {
    this.providerService.deleteProviderMetadata(this.providerId, entry.metadata_id).subscribe({
      next: () => {
        this.toast.success('Metadata removed');
        this.loadMetadata();
        this.providerService.loadProviderDetail(this.providerId, true);
      },
      error: () => this.toast.error('Failed to remove metadata'),
    });
  }

  deleteFieldMetadata(metadataId: string): void {
    this.providerService.deleteProviderMetadata(this.providerId, metadataId).subscribe({
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
    this.providerService.getProviderMetadataHistory(this.providerId, entry.metadata_id).subscribe({
      next: entries => this.historyEntries.set(entries),
    });
  }

  showFieldHistory(field: ProviderTypeMetadataField): void {
    this.historyMetadataId.set(field.metadata_id);
    this.historyMetadataName.set(field.metadata_name);
    this.editingHistoryTimestamp.set(null);
    this.providerService.getProviderMetadataHistory(this.providerId, field.metadata_id).subscribe({
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
    this.providerService.getProviderMetadataHistory(this.providerId, metaId).subscribe({
      next: entries => this.historyEntries.set(entries),
    });
  }

  // ---- History editing ----

  startEditHistory(h: MetadataHistoryEntry): void {
    this.editingHistoryTimestamp.set(h.timestamp);
    this.editHistoryValue = typeof h.value === 'object' ? JSON.stringify(h.value) : String(h.value);
    this.editHistoryTimestamp = this.toLocalDatetime(h.timestamp);
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
    const newTs = this.editHistoryTimestamp ? new Date(this.editHistoryTimestamp).toISOString() : undefined;
    this.providerService.updateProviderMetadataEntry(this.providerId, metaId, origTs, {
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
    this.providerService.deleteProviderMetadataEntry(this.providerId, metaId, h.timestamp).subscribe({
      next: () => {
        this.toast.success('Entry deleted');
        this.refreshHistory();
        this.loadMetadata();
      },
      error: () => this.toast.error('Failed to delete entry'),
    });
  }

  // ---- Helpers ----

  toLocalDatetime(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
}
