import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { ProviderService } from '../../../services/provider.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataEntry, ProviderTypeMetadataField, MetadataHistoryGrid, BulkHistoryUpdate } from '../../../models/asset.model';
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
import { ConfirmationService } from 'primeng/api';
import { MetadataHistoryTableComponent } from '../../shared/metadata-history-table.component';

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
  ],
  templateUrl: './provider-detail.component.html',
})
export class ProviderDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  private confirmationService = inject(ConfirmationService);
  providerService = inject(ProviderService);

  providerId = '';

  // Tabs
  tabs = ['Details', 'History'];
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

  // History grid state
  historyGrid = signal<MetadataHistoryGrid | null>(null);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.providerId) return;
      this.providerId = id;
      this.editing.set(false);
      this.metadataEntries.set([]);
      this.providerTypeFields.set([]);
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

  deleteProvider(): void {
    this.confirmationService.confirm({
      header: 'Delete Provider',
      message: 'Are you sure you want to delete this provider? This action cannot be undone.',
      acceptLabel: 'Delete',
      rejectLabel: 'Cancel',
      accept: () => {
        this.providerService.deleteProvider(this.providerId).subscribe({
          next: () => {
            this.toast.success('Provider deleted');
            window.history.back();
          },
          error: () => this.toast.error('Failed to delete provider'),
        });
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
    this.providerService.getProviderMetadataHistoryGrid(this.providerId).subscribe({
      next: grid => this.historyGrid.set(grid),
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
