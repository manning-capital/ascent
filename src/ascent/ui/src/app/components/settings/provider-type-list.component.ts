import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { TypeHierarchyNode } from '../../models/asset.model';
import { TreeNode, SharedModule } from 'primeng/api';
import { OrganizationChart } from 'primeng/organizationchart';
import { Select } from 'primeng/select';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';

@Component({
  selector: 'app-provider-type-list',
  standalone: true,
  imports: [FormsModule, OrganizationChart, SharedModule, Select, Card, Button, InputText],
  templateUrl: './provider-type-list.component.html',
})
export class ProviderTypeListComponent implements OnInit {
  providerService = inject(ProviderService);
  private toast = inject(ToastService);
  private router = inject(Router);

  treeData = signal<TreeNode[]>([]);
  selectedNode: TreeNode | null = null;

  showCreateForm = signal(false);
  newName = '';
  newDescription = '';
  newParentTypeId = '';

  ngOnInit(): void {
    this.providerService.loadProviderTypes();
    this.loadTree();
  }

  loadTree(): void {
    this.providerService.loadProviderTypeTree().subscribe({
      next: tree => {
        const nodes = this.toTreeNodes(tree);
        if (nodes.length > 1) {
          this.treeData.set([{
            label: 'Provider Types',
            expanded: true,
            type: 'root',
            children: nodes,
          }]);
        } else {
          this.treeData.set(nodes);
        }
      },
      error: () => this.toast.error('Failed to load type hierarchy'),
    });
  }

  private toTreeNodes(nodes: TypeHierarchyNode[]): TreeNode[] {
    return nodes.map(n => ({
      label: n.name,
      data: n,
      expanded: true,
      children: n.children.length > 0 ? this.toTreeNodes(n.children) : [],
    }));
  }

  onNodeSelect(event: any): void {
    const node = event.node;
    if (node?.data?.id) {
      this.router.navigate(['/settings/provider-types', node.data.id]);
    }
    setTimeout(() => this.selectedNode = null);
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
    this.providerService.createProviderType(
      this.newName.trim(),
      this.newDescription.trim() || undefined,
      this.newParentTypeId || undefined,
    ).subscribe({
      next: () => {
        this.toast.success('Provider type created');
        this.showCreateForm.set(false);
        this.providerService.loadProviderTypes();
        this.loadTree();
      },
      error: () => this.toast.error('Failed to create provider type'),
    });
  }
}
