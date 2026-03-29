import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../../services/asset.service';
import { ToastService } from '../../../services/toast.service';
import { TypeItem, AssetTypeMetadataField, AssetTypeProviderAssetMetadataField, MetadataType } from '../../../models/asset.model';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';
import { Checkbox } from 'primeng/checkbox';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tag } from 'primeng/tag';

@Component({
  selector: 'app-asset-type-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Select, Checkbox, TableModule, Card, Button, InputText, Tag, Skeleton],
  templateUrl: './asset-type-detail.component.html',
})
export class AssetTypeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private toast = inject(ToastService);
  assetService = inject(AssetService);

  typeId = '';
  assetType = signal<TypeItem | null>(null);
  fields = signal<AssetTypeMetadataField[]>([]);
  ownFields = computed(() => this.fields().filter(f => !f.is_inherited));
  inheritedFields = computed(() => this.fields().filter(f => f.is_inherited));

  // Provider-asset metadata fields
  paFields = signal<AssetTypeProviderAssetMetadataField[]>([]);
  ownPaFields = computed(() => this.paFields().filter(f => !f.is_inherited));
  inheritedPaFields = computed(() => this.paFields().filter(f => f.is_inherited));
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
      this.loadType();
      this.loadFields();
    });
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
    return this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id));
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
    if (!this.newMetaName.trim() || !this.newMetaDisplayName.trim()) return;
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
    return this.assetService.metadataTypes().filter(mt => !usedIds.has(mt.id));
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

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime' };
    return labels[vt] ?? vt;
  }
}
