import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { FieldService } from '../../../services/field.service';
import { ToastService } from '../../../services/toast.service';
import { AttributeItem, EntityUsage } from '../../../models/field.model';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { SafeDeleteDialogComponent } from '../../shared/safe-delete-dialog.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-attribute-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, Button, Tag, Skeleton, Tabs, TabList, Tab, Panel, SafeDeleteDialogComponent, FieldPanelComponent],
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
  tabs = ['0', '1'];
  activeTab = signal('0');

  generalFields = computed<PanelField[]>(() => {
    const attr = this.attribute();
    if (!attr) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: attr.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: attr.display_name },
      { type: 'active', key: 'isActive', label: 'Active', value: attr.is_active },
      { type: 'date', key: 'created', label: 'Created', value: attr.created_at },
      { type: 'text', key: 'description', label: 'Description', value: attr.description },
    ];
  });

  generalEditValues = signal<Record<string, any>>({});

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
    this.generalEditValues.set({
      name: this.editName,
      isActive: this.editIsActive,
      description: this.editDescription,
    });
    this.editing.set(true);
  }

  onGeneralEditChange(e: { key: string; value: any }): void {
    this.generalEditValues.update(v => ({ ...v, [e.key]: e.value }));
    if (e.key === 'name') this.editName = e.value;
    else if (e.key === 'isActive') this.editIsActive = e.value;
    else if (e.key === 'description') this.editDescription = e.value;
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
