import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { AssetService } from '../../services/asset.service';
import { ToastService } from '../../services/toast.service';
import { TypeHierarchyNode, ReparentPreview } from '../../models/asset.model';
import { Skeleton } from 'primeng/skeleton';
import { TypeHierarchyGraphComponent, TypeCreateRequest, TypeReparentRequest } from './type-hierarchy-graph.component';
import { ReparentConfirmDialogComponent, ReparentConfirmEvent } from '../shared/reparent-confirm-dialog.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';

@Component({
  selector: 'app-asset-type-list',
  standalone: true,
  imports: [Skeleton, TypeHierarchyGraphComponent, ReparentConfirmDialogComponent, AppPageHeaderComponent],
  templateUrl: './asset-type-list.component.html',
  host: { class: 'block h-full' },
})
export class AssetTypeListComponent implements OnInit {
  assetService = inject(AssetService);
  private toast = inject(ToastService);
  private router = inject(Router);

  @ViewChild(TypeHierarchyGraphComponent) graph?: TypeHierarchyGraphComponent;

  treeData = signal<TypeHierarchyNode[] | null>(null);
  reparentDialogVisible = signal(false);
  reparentPreview = signal<ReparentPreview | null>(null);
  reparenting = signal(false);
  private pendingReparent: TypeReparentRequest | null = null;

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
    this.router.navigate(['/settings/types/asset-types', nodeId]);
  }

  onCreateType(req: TypeCreateRequest): void {
    this.assetService.createAssetType(
      req.name,
      req.displayName,
      req.description,
      req.parentTypeId,
    ).subscribe({
      next: () => {
        this.toast.success('Asset type created');
        this.assetService.loadAssetTypes();
        this.loadTree();
      },
      error: () => this.toast.error('Failed to create asset type'),
    });
  }

  onReparent(req: TypeReparentRequest): void {
    this.pendingReparent = req;
    this.reparentPreview.set(null);
    this.assetService.getReparentPreview(req.childId, req.newParentId).subscribe({
      next: preview => {
        this.reparentPreview.set(preview);
        this.reparentDialogVisible.set(true);
      },
      error: () => this.toast.error('Failed to load reparent preview'),
    });
  }

  onReparentDialogClose(): void {
    this.graph?.cancelReparent();
  }

  onReparentConfirm(event: ReparentConfirmEvent): void {
    const req = this.pendingReparent;
    if (!req) return;
    this.reparenting.set(true);
    this.assetService.updateAssetType(req.childId, {
      parent_type_id: req.newParentId,
      remove_metadata_ids: event.removeMetadataIds,
      remove_provider_asset_metadata_ids: event.removeProviderAssetMetadataIds,
    }).subscribe({
      next: () => {
        this.toast.success('Type reparented');
        this.reparenting.set(false);
        this.reparentDialogVisible.set(false);
        this.assetService.loadAssetTypes();
        this.loadTree();
      },
      error: () => {
        this.toast.error('Failed to reparent type');
        this.reparenting.set(false);
      },
    });
  }
}
