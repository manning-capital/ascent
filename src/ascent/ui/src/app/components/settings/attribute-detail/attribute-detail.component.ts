import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { AttributeItem, EntityUsage } from '../../../models/field.model';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';

@Component({
  selector: 'app-attribute-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Button, InputText, Select, Tag, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent],
  templateUrl: './attribute-detail.component.html',
})
export class AttributeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  fieldService = inject(FieldService);

  attributeId = '';
  attribute = signal<AttributeItem | null>(null);
  editing = signal(false);
  activeTab = signal('0');

  editName = '';
  editDescription = '';
  editIsActive = true;

  // Delete
  showDeleteDialog = signal(false);
  usage = signal<EntityUsage | null>(null);
  deleting = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.attributeId = params.get('id')!;
      this.loadDetail();
    });
  }

  private loadDetail(): void {
    this.fieldService.getAttribute(this.attributeId).subscribe({
      next: item => {
        this.attribute.set(item);
        this.resetEditForm(item);
      },
      error: () => this.toast.error('Failed to load attribute'),
    });
  }

  private resetEditForm(item: AttributeItem): void {
    this.editName = item.name;
    this.editDescription = item.description ?? '';
    this.editIsActive = item.is_active;
  }

  startEdit(): void {
    const item = this.attribute();
    if (item) this.resetEditForm(item);
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
  }

  saveEdit(): void {
    const name = this.editName.trim();
    if (!name) return;
    this.fieldService.updateAttribute(this.attributeId, {
      name,
      description: this.editDescription.trim() || null,
      is_active: this.editIsActive,
    }).subscribe({
      next: updated => {
        this.attribute.set(updated);
        this.editing.set(false);
        this.toast.success('Attribute updated');
      },
      error: () => this.toast.error('Failed to update attribute'),
    });
  }

  openDelete(): void {
    this.usage.set(null);
    this.showDeleteDialog.set(true);
    this.fieldService.getAttributeUsage(this.attributeId).subscribe({
      next: usage => this.usage.set(usage),
      error: () => this.toast.error('Failed to load usage data'),
    });
  }

  confirmDelete(): void {
    this.deleting.set(true);
    this.fieldService.deleteAttribute(this.attributeId).subscribe({
      next: () => {
        this.toast.success('Attribute deleted');
        this.showDeleteDialog.set(false);
        this.router.navigate(['/settings/attributes']);
      },
      error: () => {
        this.toast.error('Failed to delete attribute');
        this.deleting.set(false);
      },
    });
  }
}
