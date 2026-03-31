import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CompositeService } from '../../services/composite.service';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { MultiSelect } from 'primeng/multiselect';
import { CompositeCreate, CompositeMemberCreate } from '../../models/composite.model';
import { Instrument } from '../../models/asset.model';

@Component({
  selector: 'app-composite-list',
  standalone: true,
  imports: [FormsModule, Select, MultiSelect, TableModule, InputText, Card, Button, Tag, Skeleton],
  templateUrl: './composite-list.component.html',
})
export class CompositeListComponent implements OnInit {
  private router = inject(Router);
  compositeService = inject(CompositeService);
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.compositeService.compositeTypes().map(t => t.name));

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

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

  navigateToComposite(id: string): void {
    this.router.navigate(['/settings/composites', id]);
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

  getTypeName(typeId: string): string {
    return this.compositeService.compositeTypes().find(t => t.id === typeId)?.name ?? 'Unknown';
  }
}
