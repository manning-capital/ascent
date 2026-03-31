import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { MetadataTypeItem, EntityUsage } from '../../../models/field.model';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';

@Component({
  selector: 'app-metadata-type-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Button, InputText, Select, Tag, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent],
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
  activeTab = signal('0');

  editName = '';
  editDisplayName = '';
  editDescription = '';
  editValueType = '';
  editIsActive = true;

  // Delete
  showDeleteDialog = signal(false);
  usage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.typeId = params.get('id')!;
      this.loadDetail();
    });
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
  }

  startEdit(): void {
    const item = this.metadataType();
    if (item) this.resetEditForm(item);
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  saveEdit(): void {
    const name = this.editName.trim();
    const displayName = this.editDisplayName.trim();
    if (!name || !displayName) return;
    this.fieldService.updateMetadataType(this.typeId, {
      name,
      display_name: displayName,
      description: this.editDescription.trim() || null,
      value_type: this.editValueType,
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
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime' };
    return labels[vt] ?? vt;
  }
}
