import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';

@Component({
  selector: 'app-provider-type-list',
  standalone: true,
  imports: [RouterLink, FormsModule, Card, Button, InputText],
  templateUrl: './provider-type-list.component.html',
})
export class ProviderTypeListComponent implements OnInit {
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  showCreateForm = signal(false);
  newName = '';
  newDescription = '';

  ngOnInit(): void {
    this.providerService.loadProviderTypes();
  }

  openCreate(): void {
    this.newName = '';
    this.newDescription = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newName.trim()) return;
    this.providerService.createProviderType(this.newName.trim(), this.newDescription.trim() || undefined).subscribe({
      next: () => {
        this.toast.success('Provider type created');
        this.showCreateForm.set(false);
        this.providerService.loadProviderTypes();
      },
      error: () => this.toast.error('Failed to create provider type'),
    });
  }
}
