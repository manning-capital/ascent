import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { LoadingSpinnerComponent } from '../shared/loading-spinner.component';
import { ProviderListItem, ProviderCreate } from '../../models/provider.model';

@Component({
  selector: 'app-provider-list',
  standalone: true,
  imports: [RouterLink, FormsModule, LoadingSpinnerComponent],
  templateUrl: './provider-list.component.html',
})
export class ProviderListComponent implements OnInit {
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  showCreateForm = signal(false);
  search = signal('');

  // Create form fields
  newName = '';
  newDescription = '';
  newTypeId = '';
  newExternalCode = '';
  newUrl = '';

  ngOnInit(): void {
    this.providerService.loadProviders();
    this.providerService.loadProviderTypes();
  }

  filteredProviders(): ProviderListItem[] {
    const term = this.search().toLowerCase();
    if (!term) return this.providerService.providers();
    return this.providerService.providers().filter(p =>
      p.name.toLowerCase().includes(term) ||
      (p.description?.toLowerCase().includes(term)) ||
      (p.provider_type_name?.toLowerCase().includes(term))
    );
  }

  openCreate(): void {
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
    if (!this.newName.trim() || !this.newTypeId) return;
    const data: ProviderCreate = {
      provider_type_id: this.newTypeId,
      name: this.newName.trim(),
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
