import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataTypeItem, EntityUsage } from '../../../models/field.model';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-metadata-type-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Button, Tag, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent, FieldPanelComponent],
  templateUrl: './metadata-type-detail.component.html',
})
export class MetadataTypeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  fieldService = inject(FieldService);

  typeId = '';
  metadataType = signal<MetadataTypeItem | null>(null);
  editing = signal(false);
  tabs = ['0', '1'];
  activeTab = signal('0');

  valueTypeOptions = [
    { label: 'String', value: 'string' },
    { label: 'Integer', value: 'integer' },
    { label: 'Float', value: 'float' },
    { label: 'Boolean', value: 'boolean' },
    { label: 'Date', value: 'date' },
    { label: 'Time', value: 'time' },
    { label: 'Datetime', value: 'datetime' },
    { label: 'Enum', value: 'enum' },
    { label: 'Reference', value: 'reference' },
  ];

  refTableOptions = [
    { label: 'Asset', value: 'asset' },
    { label: 'Instrument', value: 'instrument' },
    { label: 'Composite', value: 'composite' },
    { label: 'Provider', value: 'provider' },
  ];

  generalFields = computed<PanelField[]>(() => {
    const type = this.metadataType();
    if (!type) return [];
    const fields: PanelField[] = [
      { type: 'mono', key: 'name', label: 'Name', value: type.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: type.display_name },
      { type: 'tag', key: 'valueType', label: 'Value Type', value: this.valueTypeLabel(type.value_type), severity: 'secondary', options: this.valueTypeOptions },
    ];
    if (type.value_type === 'reference') {
      const refTable = type.config?.['ref_table'] ?? null;
      fields.push({ type: 'tag', key: 'refTable', label: 'Reference Table', value: this.refTableLabel(refTable), severity: 'secondary', options: this.refTableOptions });
    }
    if (type.value_type === 'enum') {
      const options = (type.config?.['options'] as string[] ?? []).join(', ');
      fields.push({ type: 'text', key: 'enumOptions', label: 'Enum Options', value: options || null, fallback: 'None' });
    }
    fields.push(
      { type: 'active', key: 'isActive', label: 'Active', value: type.is_active },
      { type: 'text', key: 'description', label: 'Description', value: type.description },
    );
    return fields;
  });

  generalEditValues = signal<Record<string, any>>({});

  editName = '';
  editDisplayName = '';
  editDescription = '';
  editValueType = '';
  editIsActive = true;
  editRefTable = '';
  editEnumOptions = '';

  // Delete
  showDeleteDialog = signal(false);
  usage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.typeId = params.get('id')!;
      const tab = this.route.snapshot.queryParamMap.get('tab');
      if (tab && this.tabs.includes(tab)) this.activeTab.set(tab);
      this.loadDetail();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  private loadDetail(): void {
    this.fieldService.getMetadataType(this.typeId).subscribe({
      next: item => {
        this.metadataType.set(item);
        this.resetEditForm(item);
      },
      error: () => this.toast.error('Failed to load metadata type'),
    });
  }

  private resetEditForm(item: MetadataTypeItem): void {
    this.editName = item.name;
    this.editDisplayName = item.display_name;
    this.editDescription = item.description ?? '';
    this.editValueType = item.value_type;
    this.editIsActive = item.is_active;
    this.editRefTable = item.config?.['ref_table'] ?? '';
    this.editEnumOptions = (item.config?.['options'] as string[] ?? []).join(', ');
  }

  startEdit(): void {
    const item = this.metadataType();
    if (!item) return;
    this.resetEditForm(item);
    this.generalEditValues.set({
      name: this.editName,
      displayName: this.editDisplayName,
      valueType: this.editValueType,
      refTable: this.editRefTable,
      enumOptions: this.editEnumOptions,
      isActive: this.editIsActive,
      description: this.editDescription,
    });
    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'displayName') this.editDisplayName = e.value;
    else if (e.key === 'valueType') this.editValueType = e.value;
    else if (e.key === 'isActive') this.editIsActive = e.value;
    else if (e.key === 'description') this.editDescription = e.value;
    else if (e.key === 'refTable') this.editRefTable = e.value;
    else if (e.key === 'enumOptions') this.editEnumOptions = e.value;
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  saveEdit(): void {
    const name = this.editName.trim();
    const displayName = this.editDisplayName.trim();
    if (!name || !displayName) return;
    let config: Record<string, any> | null = null;
    if (this.editValueType === 'reference' && this.editRefTable) {
      config = { type: 'reference', ref_table: this.editRefTable };
    } else if (this.editValueType === 'enum' && this.editEnumOptions.trim()) {
      config = { type: 'enum', options: this.editEnumOptions.split(',').map(s => s.trim()).filter(Boolean) };
    }

    this.fieldService.updateMetadataType(this.typeId, {
      name,
      display_name: displayName,
      description: this.editDescription.trim() || null,
      value_type: this.editValueType,
      config,
      is_active: this.editIsActive,
    }).subscribe({
      next: updated => {
        this.metadataType.set(updated);
        this.editing.set(false);
        this.toast.success('Metadata type updated');
      },
      error: () => this.toast.error('Failed to update metadata type'),
    });
  }

  openDelete(): void {
    this.usage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getMetadataTypeUsage(this.typeId).subscribe({
      next: usage => this.usage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.fieldService.deleteMetadataType(this.typeId).subscribe({
      next: () => {
        this.toast.success('Metadata type deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/metadata-types']);
      },
      error: () => {
        this.toast.error('Failed to delete metadata type');
        this.deleting.set(false);
      },
    });
  }

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference' };
    return labels[vt] ?? vt;
  }

  refTableLabel(rt: string | null): string {
    const labels: Record<string, string> = { asset: 'Asset', instrument: 'Instrument', composite: 'Composite', provider: 'Provider' };
    return rt ? (labels[rt] ?? rt) : '';
  }
}
