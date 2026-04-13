import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { FieldService } from '../../services/field.service';
import { ToastService } from '../../services/toast.service';
import { AttributeItem } from '../../models/field.model';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-attribute-list',
  standalone: true,
  imports: [FormsModule, Card, Button, InputText, Select, ServerTableComponent],
  templateUrl: './attribute-list.component.html',
})
export class AttributeListComponent implements OnInit {
  fieldService = inject(FieldService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  showCreateForm = signal(false);
  newName = '';
  newDisplayName = '';
  newDescription = '';

  columns: DataTableColumn<AttributeItem>[] = [
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'display_name', header: 'Display Name' },
    { field: 'is_active', header: 'Status', cellType: 'status' },
    { field: 'description', header: 'Description', valueFormatter: (p) => p.value || '-', cellClass: 'text-surface-400' },
  ];

  navigateToAttribute = (row: AttributeItem) => ['/settings/attributes', row.id];

  fetchPage = computed<ServerFetchFn<AttributeItem>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.fieldService.loadAttributesPaginated(page, pageSize, filters, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    if (qp.get('search')) this.search.set(qp.get('search')!);
    if (qp.get('is_active') != null) this.statusFilter.set(qp.get('is_active') === 'true');
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.updateUrl();
  }

  onStatusChange(value: boolean | null): void {
    this.statusFilter.set(value);
    this.updateUrl();
  }

  clearFilters(): void {
    this.search.set('');
    this.statusFilter.set(null);
    this.updateUrl();
  }

  private updateUrl(): void {
    const queryParams: Record<string, any> = {};
    const search = this.search();
    if (search) queryParams['search'] = search;
    const isActive = this.statusFilter();
    if (isActive != null) queryParams['is_active'] = isActive;
    this.router.navigate([], { relativeTo: this.route, queryParams, replaceUrl: true });
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
        this.search.update(s => s);
      },
      error: () => this.toast.error('Failed to create attribute'),
    });
  }
}
