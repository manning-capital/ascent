import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InstrumentCreate, Instrument } from '../../models/asset.model';
import { ServerTableComponent } from '../shared/data-table/server-table.component';
import type { DataTableColumn, ServerFetchFn } from '../shared/data-table/data-table.model';
import { SearchSelectComponent } from '../shared/search-select.component';

@Component({
  selector: 'app-instrument-list',
  standalone: true,
  imports: [FormsModule, Select, InputText, Card, Button, ServerTableComponent, SearchSelectComponent],
  templateUrl: './instrument-list.component.html',
})
export class InstrumentListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  search = signal('');
  statusFilter = signal<boolean | null>(null);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  columns: DataTableColumn<Instrument>[] = [
    { field: 'display_name', header: 'Display Name' },
    { field: 'name', header: 'Name', cellType: 'monospace' },
    { field: 'instrument_type_name', header: 'Type', cellType: 'link', linkRoute: (row: any) => `/settings/instrument-types/${row.instrument_type_id}` },
    { field: 'pair', header: 'Pair', sortable: false, cellClass: 'text-surface-500', valueGetter: (p: any) => `${p.data?.from_asset_name ?? ''}/${p.data?.to_asset_name ?? ''}` },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112 },
  ];

  navigateToInstrument = (row: any) => ['/settings/instruments', row.id];

  fetchPage = computed<ServerFetchFn<Instrument>>(() => {
    const search = this.search();
    const isActive = this.statusFilter();
    return (page: number, pageSize: number, sort?: { field: string; order: string }) => {
      const filters: any = {};
      if (search) filters.search = search;
      if (isActive != null) filters.is_active = isActive;
      return this.assetService.loadInstrumentsPaginated(page, pageSize, filters, sort).pipe(
        map(res => ({ items: res.items, total: res.total }))
      );
    };
  });

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  newProviderId = '';
  newFromAssetId = '';
  newToAssetId = '';
  providerSearchFn = (q: string) => this.providerService.searchProviders(q);
  assetSearchFn = (q: string) => this.assetService.searchAssets(q);

  ngOnInit(): void {
    this.assetService.loadInstrumentTypes();
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
    this.newTypeId = this.assetService.instrumentTypes()[0]?.id ?? '';
    this.newProviderId = '';
    this.newFromAssetId = '';
    this.newToAssetId = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newDisplayName.trim() || !this.newName.trim() || !this.newTypeId || !this.newProviderId || !this.newFromAssetId || !this.newToAssetId) return;
    const data: InstrumentCreate = {
      name: this.newName.trim(),
      display_name: this.newDisplayName.trim(),
      instrument_type_id: this.newTypeId,
      provider_id: this.newProviderId,
      from_asset_id: this.newFromAssetId,
      to_asset_id: this.newToAssetId,
      description: this.newDescription.trim() || undefined,
    };
    this.assetService.createInstrument(data).subscribe({
      next: () => {
        this.toast.success('Instrument created');
        this.showCreateForm.set(false);
        this.search.update(s => s);
      },
      error: () => this.toast.error('Failed to create instrument'),
    });
  }
}
