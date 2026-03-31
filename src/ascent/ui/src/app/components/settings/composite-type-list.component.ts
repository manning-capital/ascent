import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { CompositeService } from '../../services/composite.service';
import { ToastService } from '../../services/toast.service';
import { TypeHierarchyNode } from '../../models/asset.model';
import { Skeleton } from 'primeng/skeleton';
import { TypeHierarchyGraphComponent, TypeCreateRequest } from './type-hierarchy-graph.component';

@Component({
  selector: 'app-composite-type-list',
  standalone: true,
  imports: [Skeleton, TypeHierarchyGraphComponent],
  templateUrl: './composite-type-list.component.html',
  host: { class: 'block h-full' },
})
export class CompositeTypeListComponent implements OnInit {
  compositeService = inject(CompositeService);
  private toast = inject(ToastService);
  private router = inject(Router);

  @ViewChild(TypeHierarchyGraphComponent) graph?: TypeHierarchyGraphComponent;

  treeData = signal<TypeHierarchyNode[] | null>(null);

  ngOnInit(): void {
    this.compositeService.loadCompositeTypes();
    this.loadTree();
  }

  loadTree(): void {
    this.compositeService.loadCompositeTypeTree();
    // Poll signal until tree data arrives
    const check = () => {
      const tree = this.compositeService.compositeTypeTree();
      if (tree.length > 0) {
        this.treeData.set(tree);
      } else {
        setTimeout(check, 100);
      }
    };
    check();
  }

  onNodeClick(nodeId: string): void {
    this.router.navigate(['/settings/composite-types', nodeId]);
  }

  onCreateType(req: TypeCreateRequest): void {
    this.compositeService.createCompositeType({
      name: req.name,
      display_name: req.displayName,
      description: req.description,
      parent_type_id: req.parentTypeId,
      min_members: 1,
      max_members: 1,
    }).subscribe({
      next: () => {
        this.toast.success('Composite type created');
        this.compositeService.loadCompositeTypes();
        this.loadTree();
      },
      error: () => this.toast.error('Failed to create composite type'),
    });
  }
}
