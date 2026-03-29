import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { ProviderService } from '../../../services/provider.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, ProviderTypeMetadataField, MetadataHistoryGrid, BulkHistoryUpdate } from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Skeleton } from 'primeng/skeleton';
import { Select } from 'primeng/select';
import { Checkbox } from 'primeng/checkbox';
import { DatePicker } from 'primeng/datepicker';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Panel } from 'primeng/panel';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Textarea } from 'primeng/textarea';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';

@Component({
  selector: 'app-provider-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    Select,
    Checkbox,
    DatePicker,
    TableModule,
    Tag,
    Panel,
    Button,
    InputText,
    Textarea,
    Skeleton,
    Tabs, TabList, Tab,
    MetadataHistoryTableComponent,
    SafeDeleteDialogComponent,
  ],
  templateUrl: './provider-detail.component.html',
})
export class ProviderDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  providerService = inject(ProviderService);
  private fieldService = inject(FieldService);

  providerId = '';

  // Tabs
  tabs = ['Details', 'History', 'Settings'];

  // Delete
  showDeleteDialog = signal(false);
  deleteUsage = signal<EntityUsage | null>(null);
  deleting = signal(false);
  activeTab = signal('Details');

  // Edit state
  editing = signal(false);
  editName = '';
  editDescription = '';
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
      this.loadMetadata();
      this.loadProviderTypeFields();
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
    this.editDescription = provider.description ?? '';
    this.editExternalCode = provider.provider_external_code ?? '';
    this.editUrl = provider.url ?? '';
    this.editIsActive = provider.is_active;
    this.editTimestamp = new Date();

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
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  submitEdit(): void {
    if (!this.editName.trim()) return;

    const baseUpdate = this.providerService.updateProvider(this.providerId, {
      name: this.editName.trim(),
      description: this.editDescription.trim() || null,
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
