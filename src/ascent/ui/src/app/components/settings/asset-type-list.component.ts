import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { LoadingSpinnerComponent } from '../shared/loading-spinner.component';
import { TypeItem } from '../../models/asset.model';

@Component({
  selector: 'app-asset-type-list',
  standalone: true,
  imports: [RouterLink, FormsModule, LoadingSpinnerComponent],
  templateUrl: './asset-type-list.component.html',
})
export class AssetTypeListComponent implements OnInit {
  assetService = inject(AssetService);
  private toast = inject(ToastService);

  showCreateForm = signal(false);
  newName = '';
  newDescription = '';

  ngOnInit(): void {
    this.assetService.loadAssetTypes();
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
    this.assetService.createAssetType(this.newName.trim(), this.newDescription.trim() || undefined).subscribe({
      next: () => {
        this.toast.success('Asset type created');
        this.showCreateForm.set(false);
        this.assetService.loadAssetTypes();
      },
      error: () => this.toast.error('Failed to create asset type'),
    });
  }
}
