import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CompositeService } from '../../services/composite.service';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { MultiSelect } from 'primeng/multiselect';
import { CompositeCreate, CompositeMemberCreate } from '../../models/composite.model';
import { Instrument } from '../../models/asset.model';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';

@Component({
  selector: 'app-composite-list',
  standalone: true,
  imports: [FormsModule, Select, MultiSelect, InputText, Card, Button, DataTableComponent],
  templateUrl: './composite-list.component.html',
})
export class CompositeListComponent implements OnInit {
  private router = inject(Router);
  compositeService = inject(CompositeService);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.compositeService.compositeTypes().map(t => t.display_name));

  /** Composites enriched with type_display_name for filtering/sorting. */
  enrichedComposites = computed(() => {
    const types = this.compositeService.compositeTypes();
    const typeMap = new Map(types.map(t => [t.id, t.display_name]));
    return this.compositeService.composites().map(c => ({
      ...c,
      type_display_name: typeMap.get(c.composite_type_id) ?? 'Unknown',
    }));
  });

  columns: DataTableColumn[] = [
    { field: 'display_name', header: 'Display Name', filterType: 'text' },
    { field: 'name', header: 'Name', cellType: 'monospace', filterType: 'text' },
    { field: 'type_display_name', header: 'Type', cellType: 'link', linkRoute: (row: any) => `/settings/composite-types/${row.composite_type_id}`, filterType: 'select', filterOptions: this.typeNames },
    { field: 'members', header: 'Members', sortable: false, cellType: 'monospace', valueGetter: (p: any) => p.data?.members?.length ?? 0 },
    { field: 'is_active', header: 'Status', cellType: 'status', width: 112, filterType: 'select', filterOptions: [{ label: 'Active', value: true }, { label: 'Inactive', value: false }] },
  ];

  navigateToComposite = (row: any) => ['/settings/composites', row.id];

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  selectedInstruments: Instrument[] = [];

  nameTaken(): boolean {
    const n = this.newName.trim().toLowerCase();
    if (!n) return false;
    return this.compositeService.composites().some(c => c.name?.toLowerCase() === n);
  }

  ngOnInit(): void {
    this.compositeService.loadComposites();
    this.compositeService.loadCompositeTypes();
  }



  openCreate(): void {
    this.newDisplayName = '';
    this.newName = '';
    this.newDescription = '';
    this.newTypeId = this.compositeService.compositeTypes()[0]?.id ?? '';
    this.selectedInstruments = [];
    this.assetService.loadInstruments();
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newDisplayName.trim() || !this.newName.trim() || !this.newTypeId || this.nameTaken()) return;

    const members: CompositeMemberCreate[] = this.selectedInstruments.map((inst, idx) => ({
      instrument_id: inst.id,
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
        this.compositeService.loadComposites();
      },
      error: () => this.toast.error('Failed to create composite'),
    });
  }

  typeRoute(typeId: string): string {
    return `/settings/composite-types/${typeId}`;
  }
}
