import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { InputText } from 'primeng/inputtext';
import { Textarea } from 'primeng/textarea';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { MultiSelect } from 'primeng/multiselect';
import { Skeleton } from 'primeng/skeleton';
import { ProviderCreate } from '../../models/provider.model';

@Component({
  selector: 'app-provider-list',
  standalone: true,
  imports: [FormsModule, Select, TableModule, InputText, Textarea, Card, Button, Tag, MultiSelect, Skeleton],
  templateUrl: './provider-list.component.html',
})
export class ProviderListComponent implements OnInit {
  private router = inject(Router);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  typeNames = computed(() => this.providerService.providerTypes().map(t => t.name));

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  showCreateForm = signal(false);
  newDisplayName = '';
  newName = '';
  newDescription = '';
  newTypeId = '';
  newExternalCode = '';
  newUrl = '';

  ngOnInit(): void {
    this.providerService.loadProviders();
    this.providerService.loadProviderTypes();
  }

  navigateToProvider(id: string): void {
    this.router.navigate(['/settings/providers', id]);
  }

  openCreate(): void {
    this.newDisplayName = '';
    this.newName = '';
    this.newDescription = '';
    this.newTypeId = this.providerService.providerTypes()[0]?.id ?? '';
    this.newExternalCode = '';
    this.newUrl = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newName.trim() || !this.newDisplayName.trim() || !this.newTypeId) return;
    const data: ProviderCreate = {
      provider_type_id: this.newTypeId,
      name: this.newName.trim(),
      display_name: this.newDisplayName.trim(),
      description: this.newDescription.trim() || null,
      provider_external_code: this.newExternalCode.trim() || null,
      url: this.newUrl.trim() || null,
    };
    this.providerService.createProvider(data).subscribe({
      next: () => {
        this.toast.success('Provider created');
        this.showCreateForm.set(false);
        this.providerService.loadProviders();
      },
      error: () => this.toast.error('Failed to create provider'),
    });
  }
}
