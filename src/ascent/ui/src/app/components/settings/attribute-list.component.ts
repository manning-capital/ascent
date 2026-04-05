import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { AttributeItem } from '../../models/field.model';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-attribute-list',
  standalone: true,
  imports: [FormsModule, Card, Button, InputText, DataTableComponent],
  templateUrl: './attribute-list.component.html',
})
export class AttributeListComponent implements OnInit {
  fieldService = inject(FieldService);
  private toast = inject(ToastService);
  private router = inject(Router);

  showCreateForm = signal(false);
  newName = '';
  newDisplayName = '';
  newDescription = '';

  columns: DataTableColumn<AttributeItem>[] = [
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'is_active', header: 'Status', cellType: 'status' },
    { field: 'description', header: 'Description', valueFormatter: (p) => p.value || '-', cellClass: 'text-surface-400' },
  ];

  navigateToAttribute = (row: AttributeItem) => ['/settings/attributes', row.id];

  ngOnInit(): void {
    this.fieldService.loadAttributes();
  }

  openCreate(): void {
    this.newName = '';
    this.newDisplayName = '';
    this.newDescription = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    const name = this.newName.trim();
    if (!name) return;
    this.fieldService.createAttribute({
      name,
      display_name: this.newDisplayName.trim() || name,
      description: this.newDescription.trim() || undefined,
    }).subscribe({
      next: () => {
        this.toast.success('Attribute created');
        this.showCreateForm.set(false);
        this.fieldService.loadAttributes();
      },
      error: () => this.toast.error('Failed to create attribute'),
    });
  }
}
