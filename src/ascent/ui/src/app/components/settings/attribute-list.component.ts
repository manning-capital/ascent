import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { AttributeItem } from '../../models/field.model';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-attribute-list',
  standalone: true,
  imports: [FormsModule, TableModule, Card, Button, InputText, Tag, Skeleton],
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

  ngOnInit(): void {
    this.fieldService.loadAttributes();
  }

  navigateTo(event: any): void {
    const item = event.data as AttributeItem;
    if (item?.id) this.router.navigate(['/settings/attributes', item.id]);
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
