import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { CompositeService } from '../../services/composite.service';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Button } from 'primeng/button';
import { Composite, CompositeCreate, CompositeMemberCreate } from '../../models/composite.model';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import type { AppColumn, AppFetchFn, AppSeverity } from '../ui/data-table/app-column.model';
import { SearchSelectComponent, SearchOption } from '../shared/search-select.component';

@Component({
  selector: 'app-composite-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Button, AppDataTableComponent, AppPageHeaderComponent, SearchSelectComponent],
  templateUrl: './composite-list.component.html',
})
export class CompositeListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  compositeService = inject(CompositeService);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  columns: AppColumn<Composite>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    {
      field: 'composite_type_name',
      header: 'Type',
      cellType: 'link',
      linkRoute: (row: any) => `/settings/types/composite-types/${row.composite_type_id}`,
    },
    {
      field: 'members',
      header: 'Members',
      sortable: false,
      cellType: 'monospace',
      format: (_, row: any) => String(row?.members?.length ?? 0),
    },
    {
      field: 'is_active',
      header: 'Status',
      cellType: 'status',
      width: 112,
      pinned: 'right',
      tagMapper: (v): { label: string; severity: AppSeverity } => ({
        label: v ? 'Active' : 'Inactive',
        severity: v ? 'success' : 'secondary',
      }),
    },
  ];

  navigateToComposite = (row: Composite) => ['/settings/master-data/composites', row.id];

  fetchPage = computed<AppFetchFn<Composite>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page, pageSize, sort) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.compositeService
        .loadCompositesPaginated(page, pageSize, filters, sort as any)
        .pipe(map((res) => ({ items: res.items, total: res.total })));
    };
  });

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  selectedInstruments: SearchOption[] = [];
  instrumentSearchFn = (q: string) => this.assetService.searchInstruments(q);

  ngOnInit(): void {
    this.compositeService.loadCompositeTypes();
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
    this.newDisplayName = '';
    this.newName = '';
    this.newDescription = '';
    this.newTypeId = this.compositeService.compositeTypes()[0]?.id ?? '';
    this.selectedInstruments = [];
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newDisplayName.trim() || !this.newName.trim() || !this.newTypeId) return;

    const members: CompositeMemberCreate[] = this.selectedInstruments.map((opt, idx) => ({
      instrument_id: opt.value,
      order: idx + 1,
    }));

    const data: CompositeCreate = {
      name: this.newName.trim(),
      display_name: this.newDisplayName.trim(),
      composite_type_id: this.newTypeId,
      description: this.newDescription.trim() || undefined,
      members: members.length > 0 ? members : undefined,
    };
    this.compositeService.createComposite(data).subscribe({
      next: () => {
        this.toast.success('Composite created');
        this.showCreateForm.set(false);
        this.search.update((s) => s);
      },
      error: () => this.toast.error('Failed to create composite'),
    });
  }
}
