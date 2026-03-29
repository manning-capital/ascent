import {
  Component,
  Input,
  Output,
  EventEmitter,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnChanges,
  SimpleChanges,
  OnDestroy,
  signal,
  computed,
} from '@angular/core';
import * as d3 from 'd3';
import { TypeHierarchyNode } from '../../models/asset.model';

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

@Component({
  selector: 'app-asset-type-graph',
  standalone: true,
  imports: [],
  template: `
    <div
      #container
      class="w-full h-full overflow-hidden relative select-none">
      <svg #svgEl class="absolute top-0 left-0" width="100%" height="100%">
        <g #zoomGroup>
          <!-- Edges -->
          @for (edge of edgeLayouts(); track edge.key) {
            <path
              [attr.d]="edge.path"
              fill="none"
              stroke="#52525b"
              stroke-width="1.5"/>
          }

          <!-- Nodes -->
          @for (nl of nodeLayouts(); track nl.id) {
            <g class="cursor-pointer"
               (click)="nodeClick.emit(nl.id)"
               (mouseenter)="hoveredNodeId.set(nl.id)"
               (mouseleave)="hoveredNodeId.set(null)">

              <rect
                [attr.x]="nl.x - nodeWidth / 2"
                [attr.y]="nl.y - nodeHeight / 2"
                [attr.width]="nodeWidth"
                [attr.height]="nodeHeight"
                rx="8"
                fill="#18181b"
                [attr.stroke]="hoveredNodeId() === nl.id ? '#e4e4e7' : '#52525b'"
                [attr.stroke-width]="hoveredNodeId() === nl.id ? 2.5 : 1.5"/>

              <!-- Type name -->
              <text
                [attr.x]="nl.x"
                [attr.y]="nl.description ? nl.y - 2 : nl.y + 4"
                fill="white"
                font-size="12"
                font-weight="600"
                text-anchor="middle">
                {{ nl.name }}
              </text>

              <!-- Description -->
              @if (nl.description) {
                <text
                  [attr.x]="nl.x"
                  [attr.y]="nl.y + 14"
                  fill="#a1a1aa"
                  font-size="10"
                  text-anchor="middle">
                  {{ nl.description.length > 24 ? nl.description.slice(0, 22) + '…' : nl.description }}
                </text>
              }
            </g>
          }
        </g>
      </svg>

      <!-- Zoom controls -->
      <div class="absolute bottom-3 left-3 flex items-center gap-1 bg-surface/80 rounded-lg border border-edge p-1">
        <button (click)="zoomOut()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">-</button>
        <span class="text-xs text-fg-faint w-10 text-center">{{ Math.round(currentScale() * 100) }}%</span>
        <button (click)="zoomIn()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">+</button>
        <button (click)="fitToContainer()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-xs">Fit</button>
      </div>
    </div>
  `,
})
export class AssetTypeGraphComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() trees: TypeHierarchyNode[] = [];
  @Output() nodeClick = new EventEmitter<string>();

  @ViewChild('container') containerRef!: ElementRef<HTMLElement>;
  @ViewChild('svgEl') svgRef!: ElementRef<SVGSVGElement>;
  @ViewChild('zoomGroup') zoomGroupRef!: ElementRef<SVGGElement>;

  Math = Math;

  readonly nodeWidth = 180;
  readonly nodeHeight = 50;

  hoveredNodeId = signal<string | null>(null);
  currentScale = signal(1);

  private zoomBehavior!: d3.ZoomBehavior<SVGSVGElement, unknown>;
  private layoutNodes = signal<TreeNodeLayout[]>([]);
  private layoutEdges = signal<TreeEdgeLayout[]>([]);

  nodeLayouts = computed(() => this.layoutNodes());
  edgeLayouts = computed(() => this.layoutEdges());

  ngAfterViewInit(): void {
    this.setupZoom();
    this.computeLayout();
    setTimeout(() => this.fitToContainer(), 0);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['trees'] && !changes['trees'].firstChange) {
      this.computeLayout();
      setTimeout(() => this.fitToContainer(), 0);
    }
  }

  ngOnDestroy(): void {
    // D3 zoom cleans up when the element is removed
  }

  private setupZoom(): void {
    const svg = d3.select(this.svgRef.nativeElement);
    const zoomGroup = d3.select(this.zoomGroupRef.nativeElement);

    this.zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        zoomGroup.attr('transform', event.transform.toString());
        this.currentScale.set(event.transform.k);
      });

    svg.call(this.zoomBehavior);
    // Prevent double-click zoom
    svg.on('dblclick.zoom', null);
  }

  private computeLayout(): void {
    if (!this.trees || this.trees.length === 0) {
      this.layoutNodes.set([]);
      this.layoutEdges.set([]);
      return;
    }

    // Build a virtual root if multiple trees
    const virtualRoot: TypeHierarchyNode = this.trees.length === 1
      ? this.trees[0]
      : {
          id: '__root__',
          name: 'Asset Types',
          description: null,
          parent_type_id: null,
          children: this.trees,
        };

    // Build D3 hierarchy
    const root = d3.hierarchy(virtualRoot, d => d.children);

    // Use d3.tree layout (top-to-bottom)
    const treeLayout = d3.tree<TypeHierarchyNode>()
      .nodeSize([this.nodeWidth + 40, this.nodeHeight + 60]);

    treeLayout(root);

    // Collect nodes and edges
    const nodes: TreeNodeLayout[] = [];
    const edges: TreeEdgeLayout[] = [];

    root.each(d => {
      // Skip virtual root if we created one
      if (d.data.id === '__root__' && this.trees.length > 1) return;

      nodes.push({
        id: d.data.id,
        name: d.data.name,
        description: d.data.description,
        parentTypeId: d.data.parent_type_id,
        x: d.x!,
        y: d.y!,
        depth: d.depth,
        childCount: d.children?.length ?? 0,
      });
    });

    root.links().forEach(link => {
      // Skip edges from virtual root
      if (link.source.data.id === '__root__' && this.trees.length > 1) return;

      const s = link.source;
      const t = link.target;
      // Vertical bezier curve (top-to-bottom)
      const midY = (s.y! + t.y!) / 2;
      edges.push({
        key: `${s.data.id}-${t.data.id}`,
        path: `M${s.x},${s.y! + this.nodeHeight / 2} C${s.x},${midY} ${t.x},${midY} ${t.x},${t.y! - this.nodeHeight / 2}`,
      });
    });

    this.layoutNodes.set(nodes);
    this.layoutEdges.set(edges);
  }

  fitToContainer(): void {
    if (!this.svgRef?.nativeElement || !this.containerRef?.nativeElement) return;
    const nodes = this.layoutNodes();
    if (nodes.length === 0) return;

    // Compute bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodes) {
      minX = Math.min(minX, n.x - this.nodeWidth / 2);
      maxX = Math.max(maxX, n.x + this.nodeWidth / 2);
      minY = Math.min(minY, n.y - this.nodeHeight / 2);
      maxY = Math.max(maxY, n.y + this.nodeHeight / 2);
    }

    const graphWidth = maxX - minX;
    const graphHeight = maxY - minY;
    const padding = 40;

    const container = this.containerRef.nativeElement;
    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const scaleX = (cw - padding * 2) / graphWidth;
    const scaleY = (ch - padding * 2) / graphHeight;
    const scale = Math.min(scaleX, scaleY, 1.5);

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const svg = d3.select(this.svgRef.nativeElement);
    const transform = d3.zoomIdentity
      .translate(cw / 2, ch / 2)
      .scale(scale)
      .translate(-centerX, -centerY);

    svg.transition().duration(300).call(this.zoomBehavior.transform, transform);
  }

  zoomIn(): void {
    const svg = d3.select(this.svgRef.nativeElement);
    svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 1.3);
  }

  zoomOut(): void {
    const svg = d3.select(this.svgRef.nativeElement);
    svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 0.7);
  }
}
