import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CompositeService } from '../../../services/composite.service';
import { AssetService } from '../../../services/asset.service';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { CompositeTypeItem, CompositeTypeMetadataField } from '../../../models/composite.model';
import { MetadataType } from '../../../models/asset.model';
import { EntityUsage } from '../../../models/field.model';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';
import { Checkbox } from 'primeng/checkbox';
import { TableModule } from 'primeng/table';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tag } from 'primeng/tag';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-composite-type-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Select, Checkbox, TableModule, Button, InputText, Tag, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent, FieldPanelComponent],
  templateUrl: './composite-type-detail.component.html',
})
export class CompositeTypeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  compositeService = inject(CompositeService);
  assetService = inject(AssetService);
  private fieldService = inject(FieldService);

  typeId = '';
  compositeType = signal<CompositeTypeItem | null>(null);
  activeTab = signal('Details');

  generalFields = computed<PanelField[]>(() => {
    const type = this.compositeType();
    if (!type) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: type.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: type.display_name },
      { type: 'number', key: 'minMembers', label: 'Min Members', value: type.min_members, step: 1 },
      { type: 'number', key: 'maxMembers', label: 'Max Members', value: type.max_members, step: 1 },
      { type: 'text', key: 'description', label: 'Description', value: type.description },
    ];
  });

  generalEditValues = signal<Record<string, any>>({});

  // Edit state
  editing = signal(false);
  editName = '';
  editDisplayName = '';
  editDescription = '';
  editMinMembers = 1;
  editMaxMembers = 1;
  saving = signal(false);

  // Delete
  showDeleteDialog = signal(false);
  usage = signal<EntityUsage | null>(null);
  deleting = signal(false);
  fields = signal<CompositeTypeMetadataField[]>([]);
  ownFields = computed(() => this.fields().filter(f => !f.is_inherited));
  inheritedFields = computed(() => this.fields().filter(f => f.is_inherited));
  allFields = computed(() => [...this.inheritedFields(), ...this.ownFields()]);

  showAddField = signal(false);
  newFieldMetadataId = '';
  newFieldRequired = true;

  showCreateMetadata = signal(false);
  newMetaName = '';
  newMetaDisplayName = '';
  newMetaDescription = '';
  newMetaValueType = 'string';

  ngOnInit(): void {
    this.assetService.loadMetadataTypes();
    this.route.paramMap.subscribe(params => {
      this.typeId = params.get('id')!;
      this.loadType();
      this.loadFields();
    });
  }

  private loadType(): void {
    this.compositeService.loadCompositeTypes();
    const check = () => {
      const types = this.compositeService.compositeTypes();
      const found = types.find(t => t.id === this.typeId);
      if (found) {
        this.compositeType.set(found);
      } else if (types.length === 0) {
        setTimeout(check, 100);
      }
    };
    check();
  }

  loadFields(): void {
    this.compositeService.getCompositeTypeMetadata(this.typeId).subscribe({
      next: fields => this.fields.set(fields),
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
    this.compositeService.addCompositeTypeMetadata(this.typeId, {
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
    this.compositeService.removeCompositeTypeMetadata(this.typeId, metadataId).subscribe({
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

  // ---- Details Edit ----

  startEdit(): void {
    const type = this.compositeType();
    if (!type) return;
    this.editName = type.name;
    this.editDisplayName = type.display_name;
    this.editDescription = type.description ?? '';
    this.editMinMembers = type.min_members;
    this.editMaxMembers = type.max_members;
    this.generalEditValues.set({
      name: this.editName,
      displayName: this.editDisplayName,
      minMembers: this.editMinMembers,
      maxMembers: this.editMaxMembers,
      description: this.editDescription,
    });
    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'displayName') this.editDisplayName = e.value;
    else if (e.key === 'minMembers') this.editMinMembers = e.value;
    else if (e.key === 'maxMembers') this.editMaxMembers = e.value;
    else if (e.key === 'description') this.editDescription = e.value;
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  saveEdit(): void {
    const type = this.compositeType();
    if (!type) return;
    const patch: Record<string, string | number> = {};
    if (this.editName.trim() !== type.name) patch['name'] = this.editName.trim();
    if (this.editDisplayName.trim() !== type.display_name) patch['display_name'] = this.editDisplayName.trim();
    const desc = this.editDescription.trim() || '';
    if (desc !== (type.description ?? '')) patch['description'] = desc;
    if (this.editMinMembers !== type.min_members) patch['min_members'] = this.editMinMembers;
    if (this.editMaxMembers !== type.max_members) patch['max_members'] = this.editMaxMembers;
    if (Object.keys(patch).length === 0) {
      this.editing.set(false);
      return;
    }
    this.saving.set(true);
    this.compositeService.patchCompositeType(this.typeId, patch).subscribe({
      next: updated => {
        this.compositeType.set(updated);
        this.compositeService.loadCompositeTypes();
        this.toast.success('Composite type updated');
        this.editing.set(false);
        this.saving.set(false);
      },
      error: () => {
        this.toast.error('Failed to update composite type');
        this.saving.set(false);
      },
    });
  }

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime' };
    return labels[vt] ?? vt;
  }

  // ---- Delete ----

  openDelete(): void {
    this.usage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getCompositeTypeUsage(this.typeId).subscribe({
      next: usage => this.usage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.fieldService.deleteCompositeType(this.typeId).subscribe({
      next: () => {
        this.toast.success('Composite type deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/composite-types']);
      },
      error: () => {
        this.toast.error('Failed to delete composite type');
        this.deleting.set(false);
      },
    });
  }
}
