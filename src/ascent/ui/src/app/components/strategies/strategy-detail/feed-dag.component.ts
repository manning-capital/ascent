import {
  Component,
  Input,
  computed,
  signal,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnChanges,
  SimpleChanges,
  HostListener,
} from '@angular/core';
import { StrategyFeedNode, StrategyFeedDAG } from '../../../models/feed.model';

export interface FeedRunStatusOverride {
  status: string;
  is_trigger: boolean;
  feed_run_id: string;
}

interface DagNodeLayout {
  node: StrategyFeedNode;
  x: number;
  y: number;
  col: number;
}

@Component({
  selector: 'app-feed-dag',
  standalone: true,
  imports: [],
  template: `
    @if (dag && dag.nodes.length > 0) {
      <div
        #container
        class="w-full h-full overflow-hidden cursor-grab active:cursor-grabbing relative select-none"
        (mousedown)="onMouseDown($event)"
        (wheel)="onWheel($event)">

        <svg
          [attr.width]="contentWidth()"
          [attr.height]="contentHeight()"
          [style.transform]="svgTransform()"
          [style.transform-origin]="'0 0'"
          class="absolute top-0 left-0">

          <defs>
            <marker id="dag-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#52525b"/>
            </marker>
            <marker id="dag-arrow-strategy" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#f59e0b"/>
            </marker>
          </defs>

          <!-- Feed-to-feed edges -->
          @for (edge of edgeLayouts(); track edge.key) {
            <path
              [attr.d]="edge.path"
              fill="none"
              stroke="#52525b"
              stroke-width="1.5"
              marker-end="url(#dag-arrow)"
              [attr.opacity]="getEdgeOpacity(edge.key)"/>
          }

          <!-- Feed-to-strategy edges (from leaf nodes) -->
          @for (edge of strategyEdges(); track edge.key) {
            <path
              [attr.d]="edge.path"
              fill="none"
              stroke="#f59e0b"
              stroke-width="1.5"
              [attr.stroke-dasharray]="triggerPath().edges.has(edge.key) ? 'none' : '4 3'"
              [attr.opacity]="getEdgeOpacity(edge.key)"
              marker-end="url(#dag-arrow-strategy)"/>
          }

          <!-- Feed nodes -->
          @for (nl of nodeLayouts(); track nl.node.id) {
            <g class="cursor-pointer"
               (click)="navigateToFeed(nl.node.id)"
               (mouseenter)="hoveredNodeId.set(nl.node.id)"
               (mouseleave)="hoveredNodeId.set(null)"
               [attr.opacity]="getNodeOpacity(nl.node)">

              <rect
                [attr.x]="nl.x"
                [attr.y]="nl.y"
                [attr.width]="nodeWidth"
                [attr.height]="nodeHeight"
                rx="8"
                fill="#18181b"
                [attr.stroke]="nodeStroke(nl.node)"
                [attr.stroke-width]="getNodeStrokeWidth(nl.node)"/>

              <!-- Run status indicator -->
              <circle
                [attr.cx]="nl.x + 16"
                [attr.cy]="nl.y + 16"
                r="5"
                [attr.fill]="statusColor(getNodeStatus(nl.node))"/>

              <!-- Name -->
              <text
                [attr.x]="nl.x + 28"
                [attr.y]="nl.y + 20"
                fill="white"
                font-size="11"
                font-weight="600">
                {{ nl.node.name }}
              </text>

              <!-- Type + status -->
              <text
                [attr.x]="nl.x + 16"
                [attr.y]="nl.y + 38"
                fill="#a1a1aa"
                font-size="9">
                {{ nl.node.schedule ? 'Scheduled' : 'Triggered' }}
                · {{ getNodeStatusLabel(nl.node) }}
              </text>
            </g>
          }

          <!-- Strategy node -->
          <rect
            [attr.x]="strategyNodeX()"
            [attr.y]="strategyNodeY()"
            [attr.width]="strategyNodeWidth"
            [attr.height]="nodeHeight"
            rx="8"
            fill="#18181b"
            stroke="#f59e0b"
            stroke-width="1.5"/>
          <text
            [attr.x]="strategyNodeX() + strategyNodeWidth / 2"
            [attr.y]="strategyNodeY() + 20"
            fill="white"
            font-size="11"
            font-weight="600"
            text-anchor="middle">
            Strategy
          </text>
          <text
            [attr.x]="strategyNodeX() + strategyNodeWidth / 2"
            [attr.y]="strategyNodeY() + 36"
            fill="#a1a1aa"
            font-size="9"
            text-anchor="middle">
            {{ strategyName }}
          </text>
        </svg>

        <!-- Zoom controls -->
        <div class="absolute bottom-3 left-3 flex items-center gap-1 bg-surface/80 rounded-lg border border-edge p-1">
          <button (click)="zoomOut()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">-</button>
          <span class="text-xs text-fg-faint w-10 text-center">{{ Math.round(scale() * 100) }}%</span>
          <button (click)="zoomIn()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">+</button>
          <button (click)="resetView()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-xs">Fit</button>
        </div>

        <!-- Legend -->
        <div class="absolute top-3 left-3 flex items-center gap-3 text-[10px] text-fg-faint">
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-positive inline-block"></span> OK</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-negative inline-block"></span> Failed</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-warning inline-block"></span> Running</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-fg-faint inline-block"></span> No runs</div>
        </div>
      </div>
    } @else {
      <div class="flex items-center justify-center h-full text-sm text-fg-faint">
        No feeds connected to this strategy.
      </div>
    }
  `,
})
export class FeedDagComponent implements AfterViewInit, OnChanges {
  @Input() dag: StrategyFeedDAG | null = null;
  @Input() strategyName: string = '';
  @Input() feedRunStatuses: Map<string, FeedRunStatusOverride> | null = null;
  @ViewChild('container') containerRef!: ElementRef<HTMLElement>;

  Math = Math;

  readonly nodeWidth = 170;
  readonly nodeHeight = 50;
  readonly strategyNodeWidth = 130;
  readonly colGap = 70;
  readonly rowGap = 20;
  readonly padding = 30;

  // Hover state
  hoveredNodeId = signal<string | null>(null);

  // Signal mirror of @Input for use in computed()
  private feedRunStatusesSignal = signal<Map<string, FeedRunStatusOverride> | null>(null);

  // Pan & zoom state
  scale = signal(1);
  panX = signal(0);
  panY = signal(0);
  private dragging = false;
  private dragStartX = 0;
  private dragStartY = 0;
  private panStartX = 0;
  private panStartY = 0;

  svgTransform = computed(() => {
    return `translate(${this.panX()}px, ${this.panY()}px) scale(${this.scale()})`;
  });

  /** Topological column assignment (left-to-right). */
  private colAssignment = computed(() => {
    if (!this.dag || this.dag.nodes.length === 0) return new Map<string, number>();

    const nodes = this.dag.nodes;
    const nodeIds = new Set(nodes.map(n => n.id));
    const inDegree = new Map<string, number>();
    const children = new Map<string, string[]>();

    for (const n of nodes) {
      inDegree.set(n.id, 0);
      children.set(n.id, []);
    }
    for (const [from, to] of this.dag.edges) {
      if (nodeIds.has(from) && nodeIds.has(to)) {
        inDegree.set(to, (inDegree.get(to) ?? 0) + 1);
        children.get(from)!.push(to);
      }
    }

    const cols = new Map<string, number>();
    const queue: string[] = [];
    for (const [id, deg] of inDegree) {
      if (deg === 0) {
        queue.push(id);
        cols.set(id, 0);
      }
    }

    while (queue.length > 0) {
      const current = queue.shift()!;
      const currentCol = cols.get(current)!;
      for (const child of children.get(current) ?? []) {
        const newCol = currentCol + 1;
        if (!cols.has(child) || cols.get(child)! < newCol) {
          cols.set(child, newCol);
        }
        inDegree.set(child, (inDegree.get(child) ?? 0) - 1);
        if (inDegree.get(child) === 0) {
          queue.push(child);
        }
      }
    }

    for (const n of nodes) {
      if (!cols.has(n.id)) cols.set(n.id, 0);
    }

    return cols;
  });

  nodeLayouts = computed<DagNodeLayout[]>(() => {
    if (!this.dag || this.dag.nodes.length === 0) return [];

    const cols = this.colAssignment();
    const maxCol = Math.max(...cols.values());

    const colGroupsByCol = new Map<number, StrategyFeedNode[]>();
    for (const node of this.dag.nodes) {
      const col = cols.get(node.id) ?? 0;
      if (!colGroupsByCol.has(col)) colGroupsByCol.set(col, []);
      colGroupsByCol.get(col)!.push(node);
    }

    // Find max nodes in any column for centering
    const maxRows = Math.max(...[...colGroupsByCol.values()].map(g => g.length));
    const totalHeight = maxRows * this.nodeHeight + (maxRows - 1) * this.rowGap;

    const layouts: DagNodeLayout[] = [];
    for (let col = 0; col <= maxCol; col++) {
      const nodesInCol = colGroupsByCol.get(col) ?? [];
      const colHeight = nodesInCol.length * this.nodeHeight + (nodesInCol.length - 1) * this.rowGap;
      const startY = this.padding + (totalHeight - colHeight) / 2;

      nodesInCol.forEach((node, i) => {
        layouts.push({
          node,
          x: this.padding + col * (this.nodeWidth + this.colGap),
          y: startY + i * (this.nodeHeight + this.rowGap),
          col,
        });
      });
    }

    return layouts;
  });

  edgeLayouts = computed(() => {
    if (!this.dag) return [];
    const layoutMap = new Map<string, DagNodeLayout>();
    for (const nl of this.nodeLayouts()) layoutMap.set(nl.node.id, nl);

    return this.dag.edges
      .filter(([from, to]) => layoutMap.has(from) && layoutMap.has(to))
      .map(([fromId, toId]) => {
        const from = layoutMap.get(fromId)!;
        const to = layoutMap.get(toId)!;
        const x1 = from.x + this.nodeWidth;
        const y1 = from.y + this.nodeHeight / 2;
        const x2 = to.x;
        const y2 = to.y + this.nodeHeight / 2;
        const cx = (x1 + x2) / 2;
        return {
          key: `${fromId}-${toId}`,
          path: `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`,
        };
      });
  });

  /** Leaf nodes connect to the strategy node. */
  strategyEdges = computed(() => {
    if (!this.dag) return [];
    const parentIds = new Set(this.dag.edges.map(([from]) => from));
    const leafNodes = this.nodeLayouts().filter(nl => !parentIds.has(nl.node.id));
    const sx = this.strategyNodeX();
    const sy = this.strategyNodeY();

    return leafNodes.map(nl => {
      const x1 = nl.x + this.nodeWidth;
      const y1 = nl.y + this.nodeHeight / 2;
      const x2 = sx;
      const y2 = sy + this.nodeHeight / 2;
      const cx = (x1 + x2) / 2;
      return {
        key: `feed-${nl.node.id}-strategy`,
        path: `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`,
      };
    });
  });

  /** Compute trigger path: node IDs and edge keys from roots to trigger feed to strategy. */
  triggerPath = computed<{ nodes: Set<string>; edges: Set<string> }>(() => {
    const empty = { nodes: new Set<string>(), edges: new Set<string>() };
    const statuses = this.feedRunStatusesSignal();
    if (!statuses || !this.dag) return empty;

    // Find the trigger feed
    let triggerFeedId: string | null = null;
    for (const [feedId, override] of statuses.entries()) {
      if (override.is_trigger) {
        triggerFeedId = feedId;
        break;
      }
    }
    if (triggerFeedId === null) return empty;

    // BFS backward from trigger node through DAG edges
    const visited = new Set<string>([triggerFeedId]);
    const queue = [triggerFeedId];
    const pathEdges = new Set<string>();

    while (queue.length > 0) {
      const current = queue.shift()!;
      for (const [from, to] of this.dag.edges) {
        if (to === current && !visited.has(from)) {
          visited.add(from);
          queue.push(from);
          pathEdges.add(`${from}-${to}`);
        }
      }
    }

    // Include the feed-to-strategy edge for the trigger
    pathEdges.add(`feed-${triggerFeedId}-strategy`);

    return { nodes: visited, edges: pathEdges };
  });

  contentWidth = computed(() => {
    if (!this.dag || this.dag.nodes.length === 0) return 0;
    const cols = this.colAssignment();
    const maxCol = Math.max(...cols.values());
    // Feed columns + strategy column
    return this.padding * 2 + (maxCol + 1) * (this.nodeWidth + this.colGap) + this.strategyNodeWidth;
  });

  contentHeight = computed(() => {
    if (!this.dag || this.dag.nodes.length === 0) return 0;
    const cols = this.colAssignment();
    const colGroups = new Map<number, number>();
    for (const col of cols.values()) colGroups.set(col, (colGroups.get(col) ?? 0) + 1);
    const maxRows = Math.max(...colGroups.values(), 1);
    return this.padding * 2 + maxRows * this.nodeHeight + (maxRows - 1) * this.rowGap;
  });

  strategyNodeX = computed(() => {
    if (!this.dag || this.dag.nodes.length === 0) return 0;
    const cols = this.colAssignment();
    const maxCol = Math.max(...cols.values());
    return this.padding + (maxCol + 1) * (this.nodeWidth + this.colGap);
  });

  strategyNodeY = computed(() => {
    return (this.contentHeight() - this.nodeHeight) / 2;
  });

  ngAfterViewInit(): void {
    setTimeout(() => this.fitToContainer(), 0);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['dag']) {
      setTimeout(() => this.fitToContainer(), 0);
    }
    if (changes['feedRunStatuses']) {
      this.feedRunStatusesSignal.set(this.feedRunStatuses);
    }
  }

  getNodeStatus(node: StrategyFeedNode): string | null {
    if (this.feedRunStatuses) {
      if (!this.triggerPath().nodes.has(node.id)) return null;
      const override = this.feedRunStatuses.get(node.id);
      return override?.status ?? null;
    }
    return node.last_run_status;
  }

  getNodeStatusLabel(node: StrategyFeedNode): string {
    if (this.feedRunStatuses) {
      if (!this.triggerPath().nodes.has(node.id)) return 'Not Run';
      const override = this.feedRunStatuses.get(node.id);
      return override?.status ?? 'No runs';
    }
    return node.last_run_status ?? 'No runs';
  }

  getNodeOpacity(node: StrategyFeedNode): number {
    if (!this.feedRunStatuses) return 1;
    return this.triggerPath().nodes.has(node.id) ? 1 : 0.3;
  }

  getEdgeOpacity(edgeKey: string): number {
    if (!this.feedRunStatuses) return 1;
    return this.triggerPath().edges.has(edgeKey) ? 1 : 0.3;
  }

  getNodeStrokeWidth(node: StrategyFeedNode): number {
    return this.hoveredNodeId() === node.id ? 2.5 : 1.5;
  }

  nodeStroke(node: StrategyFeedNode): string {
    if (this.hoveredNodeId() === node.id) return '#e4e4e7';  // bright on hover
    if (this.feedRunStatuses && !this.triggerPath().nodes.has(node.id)) return '#52525b';
    if (node.schedule) return '#43aa8b';  // info/teal for scheduled
    return '#a78bfa';  // purple for triggered
  }

  statusColor(status: string | null): string {
    switch (status) {
      case 'COMPLETED': return '#90be6d';
      case 'FAILED': return '#f94144';
      case 'RUNNING': return '#f3722c';
      default: return '#52525b';
    }
  }

  navigateToFeed(feedId: string): void {
    const override = this.feedRunStatuses?.get(feedId);
    const runParam = override?.feed_run_id ? `?run=${override.feed_run_id}` : '';
    window.open(`/feeds/${feedId}${runParam}`, '_blank');
  }

  // --- Pan & Zoom ---
  onMouseDown(e: MouseEvent): void {
    if (e.button !== 0) return;
    this.dragging = true;
    this.dragStartX = e.clientX;
    this.dragStartY = e.clientY;
    this.panStartX = this.panX();
    this.panStartY = this.panY();
  }

  @HostListener('window:mousemove', ['$event'])
  onMouseMove(e: MouseEvent): void {
    if (!this.dragging) return;
    this.panX.set(this.panStartX + (e.clientX - this.dragStartX));
    this.panY.set(this.panStartY + (e.clientY - this.dragStartY));
  }

  @HostListener('window:mouseup')
  onMouseUp(): void {
    this.dragging = false;
  }

  onWheel(e: WheelEvent): void {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.03 : 0.03;
    const newScale = Math.min(3, Math.max(0.2, this.scale() + delta));
    this.scale.set(newScale);
  }

  zoomIn(): void {
    this.scale.set(Math.min(3, this.scale() + 0.15));
  }

  zoomOut(): void {
    this.scale.set(Math.max(0.2, this.scale() - 0.15));
  }

  resetView(): void {
    this.fitToContainer();
  }

  private fitToContainer(): void {
    if (!this.containerRef?.nativeElement) return;
    const cw = this.containerRef.nativeElement.clientWidth;
    const ch = this.containerRef.nativeElement.clientHeight;
    const sw = this.contentWidth();
    const sh = this.contentHeight();
    if (sw === 0 || sh === 0) return;

    const scaleX = cw / sw;
    const scaleY = ch / sh;
    const fitScale = Math.min(scaleX, scaleY, 1.2);
    this.scale.set(fitScale);
    this.panX.set((cw - sw * fitScale) / 2);
    this.panY.set((ch - sh * fitScale) / 2);
  }
}
