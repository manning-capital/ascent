import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { TypeHierarchyNode } from '../../models/asset.model';
import { Select } from 'primeng/select';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { AssetTypeGraphComponent } from './asset-type-graph.component';

@Component({
  selector: 'app-asset-type-list',
  standalone: true,
  imports: [FormsModule, Select, Card, Button, InputText, AssetTypeGraphComponent],
  templateUrl: './asset-type-list.component.html',
})
export class AssetTypeListComponent implements OnInit {
  assetService = inject(AssetService);
  private toast = inject(ToastService);
  private router = inject(Router);

  treeData = signal<TypeHierarchyNode[]>([]);

  showCreateForm = signal(false);
  newName = '';
  newDescription = '';
  newParentTypeId = '';

  ngOnInit(): void {
    this.assetService.loadAssetTypes();
    this.loadTree();
  }

  loadTree(): void {
    this.assetService.loadAssetTypeTree().subscribe({
      next: tree => this.treeData.set(tree),
      error: () => this.toast.error('Failed to load type hierarchy'),
    });
  }

  onNodeClick(nodeId: string): void {
    this.router.navigate(['/settings/asset-types', nodeId]);
  }

  openCreate(): void {
    this.newName = '';
    this.newDescription = '';
    this.newParentTypeId = '';
    this.showCreateForm.set(true);
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
  }

  submitCreate(): void {
    if (!this.newName.trim()) return;
    this.assetService.createAssetType(
      this.newName.trim(),
      this.newDescription.trim() || undefined,
      this.newParentTypeId || undefined,
    ).subscribe({
      next: () => {
        this.toast.success('Asset type created');
        this.showCreateForm.set(false);
        this.assetService.loadAssetTypes();
        this.loadTree();
      },
      error: () => this.toast.error('Failed to create asset type'),
    });
  }
}
