import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../../services/asset.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { TypeItem, AssetTypeMetadataField, AssetTypeProviderAssetMetadataField, MetadataType } from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';
import { Checkbox } from 'primeng/checkbox';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import type { DataTableColumn } from '../../shared/data-table/data-table.model';
import { MetadataRequiredRenderer, MetadataSourceRenderer, MetadataRemoveRenderer } from '../../shared/data-table/metadata-field-renderers';

@Component({
  selector: 'app-asset-type-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Select, Checkbox, Button, InputText, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent, FieldPanelComponent, DataTableComponent],
  templateUrl: './asset-type-detail.component.html',
})
export class AssetTypeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  assetService = inject(AssetService);
  private fieldService = inject(FieldService);

  typeId = '';
  assetType = signal<TypeItem | null>(null);
  tabs = ['Details', 'Fields', 'Settings'];
  activeTab = signal('Details');

  generalFields = computed<PanelField[]>(() => {
    const type = this.assetType();
    if (!type) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: type.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: type.display_name },
      { type: 'text', key: 'description', label: 'Description', value: type.description },
    ];
  });

  generalEditValues = signal<Record<string, any>>({});

  // Edit state
  editing = signal(false);
  editName = '';
  editDisplayName = '';
  editDescription = '';
  saving = signal(false);

  // Delete
  showDeleteDialog = signal(false);
  usage = signal<EntityUsage | null>(null);
  deleting = signal(false);
  fields = signal<AssetTypeMetadataField[]>([]);
  ownFields = computed(() => this.fields().filter(f => !f.is_inherited));
  inheritedFields = computed(() => this.fields().filter(f => f.is_inherited));
  allFields = computed(() => [...this.inheritedFields(), ...this.ownFields()]);

  // Provider-asset metadata fields
  paFields = signal<AssetTypeProviderAssetMetadataField[]>([]);
  ownPaFields = computed(() => this.paFields().filter(f => !f.is_inherited));
  inheritedPaFields = computed(() => this.paFields().filter(f => f.is_inherited));
  allPaFields = computed(() => [...this.inheritedPaFields(), ...this.ownPaFields()]);
  fieldColumns: DataTableColumn[] = [
    { field: '__index', header: '#', sortable: false, width: 50, cellType: 'custom', valueGetter: (params: any) => (params.node?.rowIndex ?? 0) + 1, cellClass: 'font-mono text-xs' },
    { field: 'metadata_name', header: 'Field Name', cellClass: (params: any) => params.data?.is_inherited ? 'font-medium text-surface-400' : 'font-medium' },
    { field: 'value_type', header: 'Value Type', cellType: 'tag', tagMapper: (value: any) => ({ label: this.valueTypeLabel(value), severity: 'secondary' }) },
    { field: 'is_required', header: 'Required', cellType: 'custom', cellRenderer: MetadataRequiredRenderer },
    { field: 'source_type_name', header: 'Source', cellType: 'custom', cellRenderer: MetadataSourceRenderer, cellRendererParams: { routePrefix: '/settings/asset-types' } },
    { field: 'metadata_description', header: 'Description', cellClass: 'text-xs text-surface-400', valueFormatter: (params: any) => params.value || '-' },
    { field: '__actions', header: '', sortable: false, width: 90, cellType: 'custom', cellRenderer: MetadataRemoveRenderer, cellRendererParams: { onRemove: (field: any) => this.removeField(field.metadata_id) } },
  ];

  paFieldColumns: DataTableColumn[] = [
    { field: '__index', header: '#', sortable: false, width: 50, cellType: 'custom', valueGetter: (params: any) => (params.node?.rowIndex ?? 0) + 1, cellClass: 'font-mono text-xs' },
    { field: 'metadata_name', header: 'Field Name', cellClass: (params: any) => params.data?.is_inherited ? 'font-medium text-surface-400' : 'font-medium' },
    { field: 'value_type', header: 'Value Type', cellType: 'tag', tagMapper: (value: any) => ({ label: this.valueTypeLabel(value), severity: 'secondary' }) },
    { field: 'is_required', header: 'Required', cellType: 'custom', cellRenderer: MetadataRequiredRenderer },
    { field: 'source_type_name', header: 'Source', cellType: 'custom', cellRenderer: MetadataSourceRenderer, cellRendererParams: { routePrefix: '/settings/asset-types' } },
    { field: 'metadata_description', header: 'Description', cellClass: 'text-xs text-surface-400', valueFormatter: (params: any) => params.value || '-' },
    { field: '__actions', header: '', sortable: false, width: 90, cellType: 'custom', cellRenderer: MetadataRemoveRenderer, cellRendererParams: { onRemove: (field: any) => this.removePaField(field.metadata_id) } },
  ];

  showAddPaField = signal(false);
  newPaFieldMetadataId = '';
  newPaFieldRequired = true;

  showAddField = signal(false);
  newFieldMetadataId = '';
  newFieldRequired = true;

  // Create new metadata type inline
  showCreateMetadata = signal(false);
  newMetaName = '';
  newMetaDisplayName = '';
  newMetaDescription = '';
  newMetaValueType = 'string';

  ngOnInit(): void {
    this.assetService.loadMetadataTypes();
    this.route.paramMap.subscribe(params => {
      this.typeId = params.get('id')!;
      const tab = this.route.snapshot.queryParamMap.get('tab');
      if (tab && this.tabs.includes(tab)) this.activeTab.set(tab);
      this.loadType();
      this.loadFields();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  private loadType(): void {
    // Find the type from the loaded list
    this.assetService.loadAssetTypes();
    const check = () => {
      const types = this.assetService.assetTypes();
      const found = types.find(t => t.id === this.typeId);
      if (found) {
        this.assetType.set(found);
      } else if (types.length === 0) {
        setTimeout(check, 100);
      }
    };
    check();
  }

  loadFields(): void {
    this.assetService.getAssetTypeMetadata(this.typeId).subscribe({
      next: fields => this.fields.set(fields),
    });
    this.assetService.getAssetTypeProviderAssetMetadata(this.typeId).subscribe({
      next: fields => this.paFields.set(fields),
    });
  }

  availableMetadataTypes(): MetadataType[] {
    const usedIds = new Set(this.fields().map(f => f.metadata_id));
    const usedNames = new Set(this.fields().map(f => f.metadata_name));
    return this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id) && !usedNames.has(mt.name));
  }

  openAddField(): void {
    const available = this.availableMetadataTypes();
    this.newFieldMetadataId = available[0]?.id ?? '';
    this.newFieldRequired = true;
    this.showAddField.set(true);
    this.showCreateMetadata.set(false);
  }

  cancelAddField(): void {
    this.showAddField.set(false);
  }

  submitAddField(): void {
    if (!this.newFieldMetadataId) return;
    this.assetService.addAssetTypeMetadata(this.typeId, {
      metadata_id: this.newFieldMetadataId,
      is_required: this.newFieldRequired,
      display_order: this.ownFields().length,
    }).subscribe({
      next: () => {
        this.toast.success('Field added');
        this.showAddField.set(false);
        this.loadFields();
      },
      error: () => this.toast.error('Failed to add field'),
    });
  }

  removeField(metadataId: string): void {
    this.assetService.removeAssetTypeMetadata(this.typeId, metadataId).subscribe({
      next: () => {
        this.toast.success('Field removed');
        this.loadFields();
      },
      error: () => this.toast.error('Failed to remove field'),
    });
  }

  openCreateMetadata(): void {
    this.newMetaName = '';
    this.newMetaDisplayName = '';
    this.newMetaDescription = '';
    this.newMetaValueType = 'string';
    this.showCreateMetadata.set(true);
  }

  cancelCreateMetadata(): void {
    this.showCreateMetadata.set(false);
  }

  submitCreateMetadata(): void {
    const name = this.newMetaName.trim();
    if (!name || !this.newMetaDisplayName.trim()) return;
    const usedNames = new Set(this.fields().map(f => f.metadata_name));
    if (usedNames.has(name)) {
      this.toast.error('A field with this name already exists');
      return;
    }
    this.assetService.createMetadataType(
      this.newMetaName.trim(),
      this.newMetaDisplayName.trim(),
      this.newMetaDescription.trim() || undefined,
      this.newMetaValueType,
    ).subscribe({
      next: () => {
        this.toast.success('Metadata type created');
        this.showCreateMetadata.set(false);
        this.assetService.loadMetadataTypes();
      },
      error: () => this.toast.error('Failed to create metadata type'),
    });
  }

  // ---- Provider-Asset Fields ----

  availablePaMetadataTypes(): MetadataType[] {
    const usedIds = new Set([
      ...this.paFields().map(f => f.metadata_id),
      ...this.fields().map(f => f.metadata_id),
    ]);
    const usedNames = new Set([
      ...this.paFields().map(f => f.metadata_name),
      ...this.fields().map(f => f.metadata_name),
    ]);
    return this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id) && !usedNames.has(mt.name));
  }

  openAddPaField(): void {
    const available = this.availablePaMetadataTypes();
    this.newPaFieldMetadataId = available[0]?.id ?? '';
    this.newPaFieldRequired = true;
    this.showAddPaField.set(true);
  }

  cancelAddPaField(): void {
    this.showAddPaField.set(false);
  }

  submitAddPaField(): void {
    if (!this.newPaFieldMetadataId) return;
    this.assetService.addAssetTypeProviderAssetMetadata(this.typeId, {
      metadata_id: this.newPaFieldMetadataId,
      is_required: this.newPaFieldRequired,
      display_order: this.ownPaFields().length,
    }).subscribe({
      next: () => {
        this.toast.success('Provider-asset field added');
        this.showAddPaField.set(false);
        this.loadFields();
      },
      error: () => this.toast.error('Failed to add field'),
    });
  }

  removePaField(metadataId: string): void {
    this.assetService.removeAssetTypeProviderAssetMetadata(this.typeId, metadataId).subscribe({
      next: () => {
        this.toast.success('Provider-asset field removed');
        this.loadFields();
      },
      error: () => this.toast.error('Failed to remove field'),
    });
  }

  // ---- Details Edit ----

  startEdit(): void {
    const type = this.assetType();
    if (!type) return;
    this.editName = type.name;
    this.editDisplayName = type.display_name;
    this.editDescription = type.description ?? '';
    this.generalEditValues.set({
      name: this.editName,
      displayName: this.editDisplayName,
      description: this.editDescription,
    });
    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'displayName') this.editDisplayName = e.value;
    else if (e.key === 'description') this.editDescription = e.value;
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  saveEdit(): void {
    const type = this.assetType();
    if (!type) return;
    const patch: Record<string, string> = {};
    if (this.editName.trim() !== type.name) patch['name'] = this.editName.trim();
    if (this.editDisplayName.trim() !== type.display_name) patch['display_name'] = this.editDisplayName.trim();
    const desc = this.editDescription.trim() || '';
    if (desc !== (type.description ?? '')) patch['description'] = desc;
    if (Object.keys(patch).length === 0) {
      this.editing.set(false);
      return;
    }
    this.saving.set(true);
    this.assetService.patchAssetType(this.typeId, patch).subscribe({
      next: updated => {
        this.assetType.set(updated);
        this.assetService.loadAssetTypes();
        this.toast.success('Asset type updated');
        this.editing.set(false);
        this.saving.set(false);
      },
      error: () => {
        this.toast.error('Failed to update asset type');
        this.saving.set(false);
      },
    });
  }

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference' };
    return labels[vt] ?? vt;
  }

  // ---- Delete ----

  openDelete(): void {
    this.usage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getAssetTypeUsage(this.typeId).subscribe({
      next: usage => this.usage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.fieldService.deleteAssetType(this.typeId).subscribe({
      next: () => {
        this.toast.success('Asset type deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/asset-types']);
      },
      error: () => {
        this.toast.error('Failed to delete asset type');
        this.deleting.set(false);
      },
    });
  }
}
