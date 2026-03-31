import {
  Component,
  Input,
  Output,
  EventEmitter,
  ViewChild,
  AfterViewInit,
  OnChanges,
  SimpleChanges,
  OnDestroy,
  signal,
  computed,
  NgZone,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import * as d3 from 'd3';
import { TypeHierarchyNode } from '../../models/asset.model';
import { GraphCanvasComponent, GraphBounds } from '../shared/graph-canvas.component';

interface TreeNodeLayout {
  id: string;
  name: string;
  description: string | null;
  parentTypeId: string | null;
  x: number;
  y: number;
  depth: number;
  childCount: number;
}

interface TreeEdgeLayout {
  key: string;
  path: string;
}

export interface TypeCreateRequest {
  name: string;
  displayName: string;
  description?: string;
  parentTypeId?: string;
}

export interface TypeReparentRequest {
  childId: string;
  newParentId: string;
}

interface DraftNode {
  parentId: string | null;
  x: number;
  y: number;
}

const DRAFT_ID = '__draft__';
const ANIM_DURATION = 300;

@Component({
  selector: 'app-type-hierarchy-graph',
  standalone: true,
  imports: [FormsModule, GraphCanvasComponent],
  template: `
    <app-graph-canvas
      [contentBounds]="bounds()"
      [ready]="ready()">

      <div graphOverlay class="absolute top-3 right-3 flex flex-col items-end gap-2">
        @if (reparentChildId()) {
          <div class="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-surface/90 border border-edge rounded-lg">
            <span class="text-fg-muted">Click a node to set as new parent</span>
            <button (click)="cancelReparent()" class="text-fg-faint hover:text-fg px-1.5 py-0.5 rounded hover:bg-fg/10">Cancel</button>
          </div>
        } @else {
          <button (click)="startRootDraft()"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-fg-muted hover:text-fg bg-surface/80 border border-edge rounded-lg hover:bg-emphasis transition-colors">
            + Add Root Type
          </button>
        }
      </div>
    </app-graph-canvas>

    <!-- Hidden draft form - values bound via ngModel, rendered into SVG via D3 foreignObject -->
    @if (draft()) {
      <div class="hidden">
        <div #draftFormContainer class="flex flex-col gap-1 p-3 h-full">
          <input
            #nameInput
            type="text"
            [(ngModel)]="draftDisplayName"
            (ngModelChange)="onDraftDisplayNameChange($event)"
            placeholder="Display name *"
            (keydown.enter)="submitDraft()"
            (keydown.escape)="cancelDraft()"
            class="w-full bg-transparent text-fg text-xs font-semibold border-b border-edge-dim outline-none placeholder:text-fg-faint px-0.5 pb-0.5"/>
          <input
            type="text"
            [(ngModel)]="draftName"
            placeholder="NAME *"
            (keydown.enter)="submitDraft()"
            (keydown.escape)="cancelDraft()"
            class="w-full bg-transparent text-fg-muted text-[10px] font-mono border-b border-edge-dim outline-none placeholder:text-fg-faint px-0.5 pb-0.5"/>
          <input
            type="text"
            [(ngModel)]="draftDescription"
            placeholder="Description (optional)"
            (keydown.enter)="submitDraft()"
            (keydown.escape)="cancelDraft()"
            class="w-full bg-transparent text-fg-muted text-[10px] border-b border-edge-dim outline-none placeholder:text-fg-faint px-0.5 pb-0.5"/>
          <div class="flex items-center justify-end gap-1 mt-auto">
            <button
              (click)="cancelDraft()"
              class="text-[10px] text-fg-faint hover:text-fg px-1.5 py-0.5 rounded hover:bg-fg/10">
              Esc
            </button>
            <button
              (click)="submitDraft()"
              class="text-[10px] text-fg font-medium px-1.5 py-0.5 rounded bg-fg/10 hover:bg-fg/20">
              Create
            </button>
          </div>
        </div>
      </div>
    }
  `,
  host: { class: 'block h-full' },
})
export class TypeHierarchyGraphComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() trees: TypeHierarchyNode[] = [];
  @Output() nodeClick = new EventEmitter<string>();
  @Output() createType = new EventEmitter<TypeCreateRequest>();
  @Output() reparent = new EventEmitter<TypeReparentRequest>();

  @ViewChild(GraphCanvasComponent) canvas!: GraphCanvasComponent;
  @ViewChild('nameInput') nameInputRef?: { nativeElement: HTMLInputElement };
  @ViewChild('draftFormContainer') draftFormRef?: { nativeElement: HTMLElement };

  readonly nodeWidth = 180;
  readonly nodeHeight = 50;
  readonly draftWidth = 200;
  readonly draftHeight = 110;

  hoveredNodeId = signal<string | null>(null);
  ready = signal(false);

  // Draft node state
  draft = signal<DraftNode | null>(null);
  draftDisplayName = '';
  draftName = '';
  draftNameManuallyEdited = false;
  draftDescription = '';

  // Reparent mode: selecting a child to move under a new parent
  reparentChildId = signal<string | null>(null);

  private layoutNodes = signal<TreeNodeLayout[]>([]);
  private layoutEdges = signal<TreeEdgeLayout[]>([]);

  private edgesGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private nodesGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private draftGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;

  nodeLayouts = computed(() => this.layoutNodes());

  bounds = computed<GraphBounds | null>(() => {
    const nodes = this.layoutNodes();
    if (nodes.length === 0) return null;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodes) {
      minX = Math.min(minX, n.x - this.nodeWidth / 2);
      maxX = Math.max(maxX, n.x + this.nodeWidth / 2);
      minY = Math.min(minY, n.y - this.nodeHeight / 2);
      maxY = Math.max(maxY, n.y + this.nodeHeight / 2);
    }
    return { minX, maxX, minY, maxY };
  });

  draftEdge = computed<TreeEdgeLayout | null>(() => {
    const d = this.draft();
    if (!d || !d.parentId) return null;
    const parent = this.layoutNodes().find(n => n.id === d.parentId);
    if (!parent) return null;

    const midY = (parent.y + this.nodeHeight / 2 + d.y - this.draftHeight / 2) / 2;
    return {
      key: `draft-edge`,
      path: `M${parent.x},${parent.y + this.nodeHeight / 2} C${parent.x},${midY} ${d.x},${midY} ${d.x},${d.y - this.draftHeight / 2}`,
    };
  });

  private viewReady = false;
  private treesWithDraft: TypeHierarchyNode[] | null = null;

  constructor(private ngZone: NgZone) {}

  ngAfterViewInit(): void {
    this.viewReady = true;

    // Create D3 groups in the canvas's zoom group (proper SVG namespace)
    const zoomGroup = d3.select(this.canvas.zoomGroupRef.nativeElement);
    this.edgesGroup = zoomGroup.append('g').attr('class', 'edges');
    this.nodesGroup = zoomGroup.append('g').attr('class', 'nodes');
    this.draftGroup = zoomGroup.append('g').attr('class', 'draft');

    this.computeLayout();
    this.renderGraph(false);
    setTimeout(() => {
      this.canvas.fitToContainer(false);
      this.ready.set(true);
    }, 0);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['trees'] && this.viewReady) {
      this.cancelDraft();
      this.computeLayout();
      this.renderGraph(false);
      setTimeout(() => this.canvas.fitToContainer(), 0);
    }
  }

  ngOnDestroy(): void {}

  // --- Draft node management ---

  onDraftDisplayNameChange(value: string): void {
    if (!this.draftNameManuallyEdited) {
      this.draftName = value.replace(/[^A-Za-z0-9\s_]/g, '').replace(/[\s]+/g, '_').toUpperCase();
    }
  }

  startDraft(parentId: string): void {
    this.draftDisplayName = '';
    this.draftName = '';
    this.draftNameManuallyEdited = false;
    this.draftDescription = '';

    // Capture old parent position before layout recomputation
    const oldParent = this.layoutNodes().find(n => n.id === parentId);
    const oldParentPos = oldParent ? { x: oldParent.x, y: oldParent.y } : null;

    const treesCopy = JSON.parse(JSON.stringify(this.trees)) as TypeHierarchyNode[];
    const parent = this.findNode(treesCopy, parentId);
    if (!parent) return;

    parent.children.push({
      id: DRAFT_ID,
      name: '',
      display_name: '',
      description: null,
      parent_type_id: parentId,
      children: [],
    });

    this.treesWithDraft = treesCopy;
    this.computeLayout(treesCopy);
    this.renderGraph(true);

    const draftLayout = this.layoutNodes().find(n => n.id === DRAFT_ID);
    if (draftLayout) {
      this.draft.set({ parentId, x: draftLayout.x, y: draftLayout.y });
      this.renderDraftNode(draftLayout.x, draftLayout.y, oldParentPos);
    }

    setTimeout(() => this.nameInputRef?.nativeElement?.focus(), 0);
  }

  startRootDraft(): void {
    this.draftDisplayName = '';
    this.draftName = '';
    this.draftNameManuallyEdited = false;
    this.draftDescription = '';

    const treesCopy = JSON.parse(JSON.stringify(this.trees)) as TypeHierarchyNode[];
    treesCopy.push({
      id: DRAFT_ID,
      name: '',
      display_name: '',
      description: null,
      parent_type_id: null,
      children: [],
    });

    this.treesWithDraft = treesCopy;
    this.computeLayout(treesCopy);
    this.renderGraph(true);

    const draftLayout = this.layoutNodes().find(n => n.id === DRAFT_ID);
    const x = draftLayout?.x ?? 0;
    const y = draftLayout?.y ?? 0;
    this.draft.set({ parentId: null, x, y });
    this.renderDraftNode(x, y);

    setTimeout(() => this.nameInputRef?.nativeElement?.focus(), 0);
  }

  cancelDraft(): void {
    this.draft.set(null);
    this.draftDisplayName = '';
    this.draftName = '';
    this.draftNameManuallyEdited = false;
    this.draftDescription = '';
    this.clearDraftNode();

    if (this.treesWithDraft) {
      this.treesWithDraft = null;
      this.computeLayout();
      this.renderGraph(true);
    }
  }

  submitDraft(): void {
    const d = this.draft();
    if (!d || !this.draftDisplayName.trim() || !this.draftName.trim()) return;

    this.treesWithDraft = null;
    this.createType.emit({
      name: this.draftName.trim(),
      displayName: this.draftDisplayName.trim(),
      description: this.draftDescription.trim() || undefined,
      parentTypeId: d.parentId ?? undefined,
    });
    this.draft.set(null);
    this.draftDisplayName = '';
    this.draftName = '';
    this.draftNameManuallyEdited = false;
    this.draftDescription = '';
    this.clearDraftNode();
  }

  startReparent(childId: string): void {
    this.cancelDraft();
    this.reparentChildId.set(childId);
    this.renderGraph(false);
  }

  cancelReparent(): void {
    this.reparentChildId.set(null);
    this.renderGraph(false);
  }

  private selectReparentTarget(newParentId: string): void {
    const childId = this.reparentChildId();
    if (!childId || childId === newParentId) return;
    this.reparentChildId.set(null);
    this.reparent.emit({ childId, newParentId });
  }

  private findNode(trees: TypeHierarchyNode[], id: string): TypeHierarchyNode | null {
    for (const node of trees) {
      if (node.id === id) return node;
      const found = this.findNode(node.children, id);
      if (found) return found;
    }
    return null;
  }

  private renderDraftNode(x: number, y: number, oldParentPos?: { x: number; y: number } | null): void {
    this.clearDraftNode();

    const dw = this.draftWidth;
    const dh = this.draftHeight;
    const d = this.draft();

    // Calculate parent shift for synchronized animation
    const newParent = d?.parentId ? this.layoutNodes().find(n => n.id === d.parentId) : null;
    const shouldAnimate = !!(oldParentPos && newParent &&
      (oldParentPos.x !== newParent.x || oldParentPos.y !== newParent.y));
    const offsetX = shouldAnimate ? oldParentPos!.x - newParent!.x : 0;
    const offsetY = shouldAnimate ? oldParentPos!.y - newParent!.y : 0;
    const easing = d3.easeCubicInOut;

    // Draft edge
    const edge = this.draftEdge();
    if (edge) {
      const edgePath = this.draftGroup.append('path')
        .attr('class', 'draft-edge')
        .attr('fill', 'none')
        .attr('stroke', 'var(--fg-faint)')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '6 3');

      if (shouldAnimate) {
        const startPath = this.makeDraftEdgePath(
          oldParentPos!.x, oldParentPos!.y, x + offsetX, y + offsetY);
        edgePath.attr('d', startPath)
          .transition().duration(ANIM_DURATION).ease(easing)
          .attr('d', edge.path);
      } else {
        edgePath.attr('d', edge.path);
      }
    }

    // Draft node rect
    const g = this.draftGroup.append('g')
      .attr('class', 'draft-node');

    if (shouldAnimate) {
      g.attr('transform', `translate(${x + offsetX},${y + offsetY})`)
        .transition().duration(ANIM_DURATION).ease(easing)
        .attr('transform', `translate(${x},${y})`);
    } else {
      g.attr('transform', `translate(${x},${y})`);
    }

    g.append('rect')
      .attr('x', -dw / 2)
      .attr('y', -dh / 2)
      .attr('width', dw)
      .attr('height', dh)
      .attr('rx', 8)
      .attr('fill', 'var(--surface)')
      .attr('stroke', 'var(--fg-muted)')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '6 3');

    // ForeignObject for the form
    const fo = g.append('foreignObject')
      .attr('x', -dw / 2)
      .attr('y', -dh / 2)
      .attr('width', dw)
      .attr('height', dh);

    // After Angular renders the hidden form, move it into the foreignObject
    setTimeout(() => {
      if (this.draftFormRef?.nativeElement) {
        const clone = this.draftFormRef.nativeElement.cloneNode(true) as HTMLElement;
        // Wire up events on the clone
        const inputs = clone.querySelectorAll('input');
        const displayNameInput = inputs[0] as HTMLInputElement;
        const nameInput = inputs[1] as HTMLInputElement;
        const descInput = inputs[2] as HTMLInputElement;
        const buttons = clone.querySelectorAll('button');
        const cancelBtn = buttons[0] as HTMLButtonElement;
        const createBtn = buttons[1] as HTMLButtonElement;

        displayNameInput?.addEventListener('input', (e) => {
          this.ngZone.run(() => {
            this.draftDisplayName = (e.target as HTMLInputElement).value;
            this.onDraftDisplayNameChange(this.draftDisplayName);
            if (!this.draftNameManuallyEdited && nameInput) {
              nameInput.value = this.draftName;
            }
          });
        });
        nameInput?.addEventListener('input', (e) => {
          this.ngZone.run(() => {
            this.draftNameManuallyEdited = true;
            this.draftName = (e.target as HTMLInputElement).value;
          });
        });
        descInput?.addEventListener('input', (e) => {
          this.ngZone.run(() => { this.draftDescription = (e.target as HTMLInputElement).value; });
        });
        for (const input of [displayNameInput, nameInput, descInput]) {
          input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.ngZone.run(() => this.submitDraft());
            if (e.key === 'Escape') this.ngZone.run(() => this.cancelDraft());
          });
        }
        cancelBtn?.addEventListener('click', (e) => {
          e.stopPropagation();
          this.ngZone.run(() => this.cancelDraft());
        });
        createBtn?.addEventListener('click', (e) => {
          e.stopPropagation();
          this.ngZone.run(() => this.submitDraft());
        });
        clone.addEventListener('click', (e) => e.stopPropagation());

        fo.node()?.appendChild(clone);
        nameInput?.focus();
      }
    }, 0);
  }

  private clearDraftNode(): void {
    if (this.draftGroup) {
      this.draftGroup.selectAll('*').remove();
    }
  }

  private makeDraftEdgePath(parentX: number, parentY: number, draftX: number, draftY: number): string {
    const midY = (parentY + this.nodeHeight / 2 + draftY - this.draftHeight / 2) / 2;
    return `M${parentX},${parentY + this.nodeHeight / 2} C${parentX},${midY} ${draftX},${midY} ${draftX},${draftY - this.draftHeight / 2}`;
  }

  // --- D3 rendering (nodes + edges in sync) ---

  private renderGraph(animate: boolean): void {
    this.renderEdges(animate);
    this.renderNodes(animate);
  }

  private renderEdges(animate: boolean): void {
    if (!this.edgesGroup) return;

    const edges = this.layoutEdges();
    const easing = d3.easeCubicInOut;

    const paths = this.edgesGroup.selectAll<SVGPathElement, TreeEdgeLayout>('path')
      .data(edges, d => d.key);

    paths.enter()
      .append('path')
      .attr('fill', 'none')
      .attr('stroke', 'var(--fg-faint)')
      .attr('stroke-width', 1.5)
      .attr('d', d => d.path);

    if (animate) {
      paths.transition().duration(ANIM_DURATION).ease(easing)
        .attr('d', d => d.path);
    } else {
      paths.attr('d', d => d.path);
    }

    paths.exit().remove();
  }

  private renderNodes(animate: boolean): void {
    if (!this.nodesGroup) return;

    const nodes = this.layoutNodes().filter(n => n.id !== DRAFT_ID);
    const easing = d3.easeCubicInOut;
    const nw = this.nodeWidth;
    const nh = this.nodeHeight;
    const component = this;

    const groups = this.nodesGroup.selectAll<SVGGElement, TreeNodeLayout>('g.node-group')
      .data(nodes, d => d.id);

    const enter = groups.enter()
      .append('g')
      .attr('class', 'node-group')
      .attr('cursor', 'pointer')
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .on('click', function(_event, d) {
        const reparentId = component.reparentChildId();
        if (reparentId) {
          if (reparentId !== d.id) {
            component.ngZone.run(() => component.selectReparentTarget(d.id));
          }
        } else if (!component.draft()) {
          component.ngZone.run(() => component.nodeClick.emit(d.id));
        }
      })
      .on('mouseenter', function(_event, d) {
        component.ngZone.run(() => component.hoveredNodeId.set(d.id));
        const reparentId = component.reparentChildId();
        if (reparentId && reparentId !== d.id) {
          d3.select(this).select('rect.node-bg')
            .attr('stroke', 'var(--graph-accent-2)')
            .attr('stroke-width', 2.5);
        } else {
          d3.select(this).select('rect.node-bg')
            .attr('stroke', 'var(--fg-muted)')
            .attr('stroke-width', 2.5);
        }
        if (!component.draft() && !reparentId) {
          d3.select(this).select('g.add-btn').attr('visibility', 'visible');
          d3.select(this).select('g.move-btn').attr('visibility', 'visible');
        }
      })
      .on('mouseleave', function(_event, _d) {
        component.ngZone.run(() => component.hoveredNodeId.set(null));
        const reparentId = component.reparentChildId();
        d3.select(this).select('rect.node-bg')
          .attr('stroke', reparentId && _d.id === reparentId ? 'var(--graph-accent-1)' : 'var(--edge)')
          .attr('stroke-width', reparentId && _d.id === reparentId ? 2.5 : 1.5);
        d3.select(this).select('g.add-btn').attr('visibility', 'hidden');
        d3.select(this).select('g.move-btn').attr('visibility', 'hidden');
      });

    enter.append('rect')
      .attr('class', 'node-bg')
      .attr('x', -nw / 2)
      .attr('y', -nh / 2)
      .attr('width', nw)
      .attr('height', nh)
      .attr('rx', 8)
      .attr('fill', 'var(--surface)')
      .attr('stroke', 'var(--edge)')
      .attr('stroke-width', 1.5);

    enter.append('text')
      .attr('class', 'node-name')
      .attr('x', 0)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--fg)')
      .attr('font-size', 12)
      .attr('font-weight', 600)
      .attr('y', d => d.description ? -2 : 4)
      .text(d => d.name);

    enter.append('text')
      .attr('class', 'node-desc')
      .attr('x', 0)
      .attr('y', 14)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--fg-muted)')
      .attr('font-size', 10)
      .text(d => {
        if (!d.description) return '';
        return d.description.length > 24 ? d.description.slice(0, 22) + '…' : d.description;
      });

    const addBtn = enter.append('g')
      .attr('class', 'add-btn')
      .attr('visibility', 'hidden')
      .attr('cursor', 'pointer')
      .on('click', function(event, d) {
        event.stopPropagation();
        component.ngZone.run(() => component.startDraft(d.id));
      });

    addBtn.append('circle')
      .attr('cx', 0)
      .attr('cy', nh / 2)
      .attr('r', 10)
      .attr('fill', 'var(--elevated)')
      .attr('stroke', 'var(--edge)')
      .attr('stroke-width', 1.5);

    addBtn.append('text')
      .attr('x', 0)
      .attr('y', nh / 2 + 4)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--fg-muted)')
      .attr('font-size', 13)
      .attr('font-weight', 600)
      .text('+');

    // Move/reparent button (top-right corner)
    const moveBtn = enter.append('g')
      .attr('class', 'move-btn')
      .attr('visibility', 'hidden')
      .attr('cursor', 'pointer')
      .on('click', function(event, d) {
        event.stopPropagation();
        component.ngZone.run(() => component.startReparent(d.id));
      });

    moveBtn.append('circle')
      .attr('cx', nw / 2)
      .attr('cy', -nh / 2)
      .attr('r', 10)
      .attr('fill', 'var(--elevated)')
      .attr('stroke', 'var(--edge)')
      .attr('stroke-width', 1.5);

    moveBtn.append('text')
      .attr('x', nw / 2)
      .attr('y', -nh / 2 + 4)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--fg-muted)')
      .attr('font-size', 11)
      .attr('font-weight', 600)
      .text('↗');

    if (animate) {
      groups.transition().duration(ANIM_DURATION).ease(easing)
        .attr('transform', d => `translate(${d.x},${d.y})`);
    } else {
      groups.attr('transform', d => `translate(${d.x},${d.y})`);
    }

    groups.select('text.node-name')
      .attr('y', d => d.description ? -2 : 4)
      .text(d => d.name);
    groups.select('text.node-desc')
      .text(d => {
        if (!d.description) return '';
        return d.description.length > 24 ? d.description.slice(0, 22) + '…' : d.description;
      });

    if (this.draft()) {
      this.nodesGroup.selectAll('g.add-btn').attr('visibility', 'hidden');
      this.nodesGroup.selectAll('g.move-btn').attr('visibility', 'hidden');
    }

    // Reparent mode: highlight selected child, change cursor on valid targets
    const reparentId = this.reparentChildId();
    if (reparentId) {
      this.nodesGroup.selectAll('g.add-btn').attr('visibility', 'hidden');
      this.nodesGroup.selectAll('g.move-btn').attr('visibility', 'hidden');
      this.nodesGroup.selectAll<SVGGElement, TreeNodeLayout>('g.node-group').each(function(d) {
        const g = d3.select(this);
        if (d.id === reparentId) {
          g.select('rect.node-bg')
            .attr('stroke', 'var(--graph-accent-1)')
            .attr('stroke-width', 2.5);
        } else {
          g.attr('cursor', 'copy');
          g.select('rect.node-bg')
            .attr('stroke-dasharray', '4 2');
        }
      });
    } else {
      this.nodesGroup.selectAll<SVGGElement, TreeNodeLayout>('g.node-group').each(function() {
        const g = d3.select(this);
        g.attr('cursor', 'pointer');
        g.select('rect.node-bg')
          .attr('stroke-dasharray', null)
          .attr('stroke', 'var(--edge)')
          .attr('stroke-width', 1.5);
      });
    }

    groups.exit().remove();
  }

  // --- Layout ---

  private computeLayout(treesOverride?: TypeHierarchyNode[]): void {
    const trees = treesOverride ?? this.trees;
    if (!trees || trees.length === 0) {
      this.layoutNodes.set([]);
      this.layoutEdges.set([]);
      return;
    }

    const useVirtualRoot = trees.length > 1;
    const virtualRoot: TypeHierarchyNode = useVirtualRoot
      ? {
          id: '__root__',
          name: '',
          display_name: '',
          description: null,
          parent_type_id: null,
          children: trees,
        }
      : trees[0];

    const root = d3.hierarchy(virtualRoot, d => d.children);

    const treeLayout = d3.tree<TypeHierarchyNode>()
      .nodeSize([this.nodeWidth + 40, this.nodeHeight + 60]);

    treeLayout(root);

    const nodes: TreeNodeLayout[] = [];
    const edges: TreeEdgeLayout[] = [];

    root.each(d => {
      if (d.data.id === '__root__' && useVirtualRoot) return;

      nodes.push({
        id: d.data.id,
        name: d.data.display_name,
        description: d.data.description,
        parentTypeId: d.data.parent_type_id,
        x: d.x!,
        y: d.y!,
        depth: d.depth,
        childCount: d.children?.length ?? 0,
      });
    });

    root.links().forEach(link => {
      if (link.source.data.id === '__root__' && useVirtualRoot) return;
      if (link.target.data.id === DRAFT_ID) return;

      const s = link.source;
      const t = link.target;
      const midY = (s.y! + t.y!) / 2;
      edges.push({
        key: `${s.data.id}-${t.data.id}`,
        path: `M${s.x},${s.y! + this.nodeHeight / 2} C${s.x},${midY} ${t.x},${midY} ${t.x},${t.y! - this.nodeHeight / 2}`,
      });
    });

    this.layoutNodes.set(nodes);
    this.layoutEdges.set(edges);
  }
}
