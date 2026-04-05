import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { MetadataTypeItem } from '../../models/field.model';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-metadata-type-list',
  standalone: true,
  imports: [FormsModule, Card, Button, InputText, Select, DataTableComponent],
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

  private valueTypeLabels: Record<string, string> = {
    string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean',
    date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference',
  };

  columns: DataTableColumn<MetadataTypeItem>[] = [
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'display_name', header: 'Display Name' },
    { field: 'value_type', header: 'Value Type', cellType: 'tag', tagMapper: (v) => ({ label: this.valueTypeLabels[v] ?? v, severity: 'secondary' }) },
    { field: 'is_active', header: 'Status', cellType: 'status' },
    { field: 'description', header: 'Description', valueFormatter: (p) => p.value || '-', cellClass: 'text-surface-400' },
  ];

  navigateToMetadataType = (row: MetadataTypeItem) => ['/settings/metadata-types', row.id];

  ngOnInit(): void {
    this.fieldService.loadMetadataTypes();
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
