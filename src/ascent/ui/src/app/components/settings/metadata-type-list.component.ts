import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { MetadataTypeItem } from '../../models/field.model';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-metadata-type-list',
  standalone: true,
  imports: [FormsModule, TableModule, Card, Button, InputText, Select, Tag, Skeleton],
  templateUrl: './metadata-type-list.component.html',
})
export class MetadataTypeListComponent implements OnInit {
  fieldService = inject(FieldService);
  private toast = inject(ToastService);
  private router = inject(Router);

  showCreateForm = signal(false);
  newName = '';
  newDisplayName = '';
  newDescription = '';
  newValueType = 'string';

  ngOnInit(): void {
    this.fieldService.loadMetadataTypes();
  }

  navigateTo(event: any): void {
    const item = event.data as MetadataTypeItem;
    if (item?.id) this.router.navigate(['/settings/metadata-types', item.id]);
  }

  openCreate(): void {
    this.newName = '';
    this.newDisplayName = '';
    this.newDescription = '';
    this.newValueType = 'string';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    const name = this.newName.trim();
    const displayName = this.newDisplayName.trim();
    if (!name || !displayName) return;
    this.fieldService.createMetadataType({
      name,
      display_name: displayName,
      description: this.newDescription.trim() || undefined,
      value_type: this.newValueType,
    }).subscribe({
      next: () => {
        this.toast.success('Metadata type created');
        this.showCreateForm.set(false);
        this.fieldService.loadMetadataTypes();
      },
      error: () => this.toast.error('Failed to create metadata type'),
    });
  }

  valueTypeLabel(vt: string): string {
    const labels: Record<string, string> = { string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean', date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference' };
    return labels[vt] ?? vt;
  }
}
