import {
  Component,
  Input,
  computed,
  signal,
  AfterViewInit,
  OnChanges,
  SimpleChanges,
  NgZone,
  ViewChild,
} from '@angular/core';
import * as d3 from 'd3';
import { StrategyFeedNode, StrategyFeedDAG } from '../../../models/feed.model';
import { GraphCanvasComponent, GraphBounds } from '../../shared/graph-canvas.component';

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

interface DagEdgeLayout {
  key: string;
  path: string;
}

@Component({
  selector: 'app-feed-dag',
  standalone: true,
  imports: [GraphCanvasComponent],
  host: { class: 'block h-full' },
  template: `
    @if (dag && dag.nodes.length > 0) {
      <app-graph-canvas
        [contentBounds]="bounds()"
        [ready]="ready()"
        [maxFitScale]="1.2">

        <!-- Legend -->
        <div graphOverlay class="absolute top-3 left-3 flex items-center gap-3 text-[10px] text-fg-faint">
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-positive inline-block"></span> OK</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-negative inline-block"></span> Failed</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-warning inline-block"></span> Running</div>
          <div class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-fg-faint inline-block"></span> No runs</div>
        </div>
      </app-graph-canvas>
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

  @ViewChild(GraphCanvasComponent) canvas?: GraphCanvasComponent;

  readonly nodeWidth = 170;
  readonly nodeHeight = 50;
  readonly strategyNodeWidth = 130;
  readonly colGap = 70;
  readonly rowGap = 20;
  readonly padding = 30;

  hoveredNodeId = signal<string | null>(null);
  ready = signal(false);

  private feedRunStatusesSignal = signal<Map<string, FeedRunStatusOverride> | null>(null);
  private viewReady = false;

  // D3 groups created programmatically
  private feedEdgesGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private strategyEdgesGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private feedNodesGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private strategyNodeGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;

  constructor(private ngZone: NgZone) {}

  // --- Layout computeds ---

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

  edgeLayouts = computed<DagEdgeLayout[]>(() => {
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

  strategyEdgesComputed = computed<DagEdgeLayout[]>(() => {
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

  triggerPath = computed<{ nodes: Set<string>; edges: Set<string> }>(() => {
    const empty = { nodes: new Set<string>(), edges: new Set<string>() };
    const statuses = this.feedRunStatusesSignal();
    if (!statuses || !this.dag) return empty;

    let triggerFeedId: string | null = null;
    for (const [feedId, override] of statuses.entries()) {
      if (override.is_trigger) {
        triggerFeedId = feedId;
        break;
      }
    }
    if (triggerFeedId === null) return empty;

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

    pathEdges.add(`feed-${triggerFeedId}-strategy`);
    return { nodes: visited, edges: pathEdges };
  });

  contentWidth = computed(() => {
    if (!this.dag || this.dag.nodes.length === 0) return 0;
    const cols = this.colAssignment();
    const maxCol = Math.max(...cols.values());
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

  bounds = computed<GraphBounds | null>(() => {
    const w = this.contentWidth();
    const h = this.contentHeight();
    if (w === 0 || h === 0) return null;
    return { minX: 0, maxX: w, minY: 0, maxY: h };
  });

  // --- Lifecycle ---

  ngAfterViewInit(): void {
    this.viewReady = true;
    if (this.dag && this.dag.nodes.length > 0) {
      this.initD3Groups();
      this.renderGraph();
      setTimeout(() => {
        this.canvas?.fitToContainer(false);
        this.ready.set(true);
      }, 0);
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['feedRunStatuses']) {
      this.feedRunStatusesSignal.set(this.feedRunStatuses);
    }
    if (changes['dag'] && this.viewReady) {
      this.ready.set(false);
      setTimeout(() => {
        if (this.dag && this.dag.nodes.length > 0 && this.canvas) {
          this.initD3Groups();
          this.renderGraph();
          setTimeout(() => {
            this.canvas?.fitToContainer(false);
            this.ready.set(true);
          }, 0);
        }
      }, 0);
    } else if (changes['feedRunStatuses'] && this.viewReady && this.feedNodesGroup) {
      this.renderGraph();
    }
  }

  // --- Status helpers ---

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

  nodeStroke(node: StrategyFeedNode): string {
    if (this.hoveredNodeId() === node.id) return 'var(--fg-muted)';
    if (this.feedRunStatuses && !this.triggerPath().nodes.has(node.id)) return 'var(--fg-faint)';
    if (node.schedule) return 'var(--graph-accent-2)';
    return 'var(--graph-accent-3)';
  }

  statusColor(status: string | null): string {
    switch (status) {
      case 'COMPLETED': return 'var(--positive)';
      case 'FAILED': return 'var(--negative)';
      case 'RUNNING': return 'var(--warning)';
      default: return 'var(--fg-faint)';
    }
  }

  navigateToFeed(feedId: string): void {
    const override = this.feedRunStatuses?.get(feedId);
    const runParam = override?.feed_run_id ? `?run=${override.feed_run_id}` : '';
    window.open(`/feeds/${feedId}${runParam}`, '_blank');
  }

  // --- D3 setup and rendering ---

  private initD3Groups(): void {
    if (!this.canvas) return;
    const zoomGroup = d3.select(this.canvas.zoomGroupRef.nativeElement);

    // Clear any previous groups (re-init on dag change)
    zoomGroup.selectAll('*').remove();

    // Create arrow markers in the SVG defs
    const svg = d3.select(this.canvas.svgRef.nativeElement);
    let defs = svg.select<SVGDefsElement>('defs');
    if (defs.empty()) {
      defs = svg.insert('defs', ':first-child');
    }
    // Remove old markers and re-add
    defs.selectAll('marker').remove();

    const arrow = defs.append('marker')
      .attr('id', 'dag-arrow')
      .attr('markerWidth', 8).attr('markerHeight', 6)
      .attr('refX', 8).attr('refY', 3).attr('orient', 'auto');
    arrow.append('polygon').attr('points', '0 0, 8 3, 0 6').attr('fill', 'var(--fg-faint)');

    const arrowStrategy = defs.append('marker')
      .attr('id', 'dag-arrow-strategy')
      .attr('markerWidth', 8).attr('markerHeight', 6)
      .attr('refX', 8).attr('refY', 3).attr('orient', 'auto');
    arrowStrategy.append('polygon').attr('points', '0 0, 8 3, 0 6').attr('fill', 'var(--graph-accent-1)');

    this.feedEdgesGroup = zoomGroup.append('g').attr('class', 'feed-edges');
    this.strategyEdgesGroup = zoomGroup.append('g').attr('class', 'strategy-edges');
    this.feedNodesGroup = zoomGroup.append('g').attr('class', 'feed-nodes');
    this.strategyNodeGroup = zoomGroup.append('g').attr('class', 'strategy-node-container');
  }

  private renderGraph(): void {
    this.renderFeedEdges();
    this.renderStrategyEdges();
    this.renderFeedNodes();
    this.renderStrategyNode();
  }

  private renderFeedEdges(): void {
    if (!this.feedEdgesGroup) return;

    const edges = this.edgeLayouts();
    const component = this;

    const paths = this.feedEdgesGroup.selectAll<SVGPathElement, DagEdgeLayout>('path')
      .data(edges, d => d.key);

    paths.enter()
      .append('path')
      .attr('fill', 'none')
      .attr('stroke', 'var(--fg-faint)')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#dag-arrow)')
      .attr('d', d => d.path)
      .attr('opacity', d => component.getEdgeOpacity(d.key));

    paths
      .attr('d', d => d.path)
      .attr('opacity', d => component.getEdgeOpacity(d.key));

    paths.exit().remove();
  }

  private renderStrategyEdges(): void {
    if (!this.strategyEdgesGroup) return;

    const edges = this.strategyEdgesComputed();
    const component = this;
    const tp = this.triggerPath();

    const paths = this.strategyEdgesGroup.selectAll<SVGPathElement, DagEdgeLayout>('path')
      .data(edges, d => d.key);

    paths.enter()
      .append('path')
      .attr('fill', 'none')
      .attr('stroke', 'var(--graph-accent-1)')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#dag-arrow-strategy)')
      .attr('d', d => d.path)
      .attr('stroke-dasharray', d => tp.edges.has(d.key) ? 'none' : '4 3')
      .attr('opacity', d => component.getEdgeOpacity(d.key));

    paths
      .attr('d', d => d.path)
      .attr('stroke-dasharray', d => tp.edges.has(d.key) ? 'none' : '4 3')
      .attr('opacity', d => component.getEdgeOpacity(d.key));

    paths.exit().remove();
  }

  private renderFeedNodes(): void {
    if (!this.feedNodesGroup) return;

    const nodes = this.nodeLayouts();
    const nw = this.nodeWidth;
    const nh = this.nodeHeight;
    const component = this;

    const groups = this.feedNodesGroup.selectAll<SVGGElement, DagNodeLayout>('g.feed-node')
      .data(nodes, d => d.node.id);

    const enter = groups.enter()
      .append('g')
      .attr('class', 'feed-node')
      .attr('cursor', 'pointer')
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .on('click', function(_event, d) {
        component.ngZone.run(() => component.navigateToFeed(d.node.id));
      })
      .on('mouseenter', function(_event, d) {
        component.ngZone.run(() => component.hoveredNodeId.set(d.node.id));
        d3.select(this).select('rect.feed-bg')
          .attr('stroke', 'var(--fg-muted)')
          .attr('stroke-width', 2.5);
      })
      .on('mouseleave', function(_event, d) {
        component.ngZone.run(() => component.hoveredNodeId.set(null));
        d3.select(this).select('rect.feed-bg')
          .attr('stroke', component.nodeStroke(d.node))
          .attr('stroke-width', 1.5);
      });

    enter.append('rect')
      .attr('class', 'feed-bg')
      .attr('x', 0).attr('y', 0)
      .attr('width', nw).attr('height', nh)
      .attr('rx', 8)
      .attr('fill', 'var(--surface)')
      .attr('stroke', d => component.nodeStroke(d.node))
      .attr('stroke-width', 1.5);

    enter.append('circle')
      .attr('class', 'status-dot')
      .attr('cx', 16).attr('cy', 16).attr('r', 5)
      .attr('fill', d => component.statusColor(component.getNodeStatus(d.node)));

    enter.append('text')
      .attr('class', 'feed-name')
      .attr('x', 28).attr('y', 20)
      .attr('fill', 'var(--fg)')
      .attr('font-size', 11).attr('font-weight', 600)
      .text(d => d.node.name);

    enter.append('text')
      .attr('class', 'feed-type')
      .attr('x', 16).attr('y', 38)
      .attr('fill', 'var(--fg-muted)')
      .attr('font-size', 9)
      .text(d => `${d.node.schedule ? 'Scheduled' : 'Triggered'} · ${component.getNodeStatusLabel(d.node)}`);

    enter.attr('opacity', d => component.getNodeOpacity(d.node));

    // Update
    groups
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .attr('opacity', d => component.getNodeOpacity(d.node));

    groups.select('rect.feed-bg')
      .attr('stroke', d => component.nodeStroke(d.node));

    groups.select('circle.status-dot')
      .attr('fill', d => component.statusColor(component.getNodeStatus(d.node)));

    groups.select('text.feed-name')
      .text(d => d.node.name);

    groups.select('text.feed-type')
      .text(d => `${d.node.schedule ? 'Scheduled' : 'Triggered'} · ${component.getNodeStatusLabel(d.node)}`);

    groups.exit().remove();
  }

  private renderStrategyNode(): void {
    if (!this.strategyNodeGroup) return;

    const sx = this.strategyNodeX();
    const sy = this.strategyNodeY();
    const snw = this.strategyNodeWidth;
    const nh = this.nodeHeight;
    const name = this.strategyName;

    const data = this.dag && this.dag.nodes.length > 0 ? [{ x: sx, y: sy }] : [];

    const groups = this.strategyNodeGroup.selectAll<SVGGElement, { x: number; y: number }>('g.strategy-node')
      .data(data);

    const enter = groups.enter()
      .append('g')
      .attr('class', 'strategy-node')
      .attr('transform', d => `translate(${d.x},${d.y})`);

    enter.append('rect')
      .attr('x', 0).attr('y', 0)
      .attr('width', snw).attr('height', nh)
      .attr('rx', 8)
      .attr('fill', 'var(--surface)')
      .attr('stroke', 'var(--graph-accent-1)')
      .attr('stroke-width', 1.5);

    enter.append('text')
      .attr('class', 'strat-label')
      .attr('x', snw / 2).attr('y', 20)
      .attr('fill', 'var(--fg)')
      .attr('font-size', 11).attr('font-weight', 600)
      .attr('text-anchor', 'middle')
      .text('Strategy');

    enter.append('text')
      .attr('class', 'strat-name')
      .attr('x', snw / 2).attr('y', 36)
      .attr('fill', 'var(--fg-muted)')
      .attr('font-size', 9)
      .attr('text-anchor', 'middle')
      .text(name);

    groups.attr('transform', d => `translate(${d.x},${d.y})`);
    groups.select('text.strat-name').text(name);

    groups.exit().remove();
  }
}
