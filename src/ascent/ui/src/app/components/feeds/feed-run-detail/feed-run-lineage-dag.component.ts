import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';
import * as d3 from 'd3';
import { FeedService } from '../../../services/feed.service';
import {
  FeedRunLineageResponse,
  FeedRunListItem,
} from '../../../models/feed.model';
import { AppEmptyStateComponent } from '../../ui/empty-state/app-empty-state.component';

interface DagNode {
  id: string;
  layer: number;
  label: string;
  sublabel?: string;
  status: string;
  color: string;
  routeFn: () => void;
  x?: number;
  y?: number;
}

@Component({
  selector: 'app-feed-run-lineage-dag',
  standalone: true,
  imports: [AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; height: 100%; }
    .dag-tooltip {
      position: fixed;
      pointer-events: none;
      z-index: 9999;
      background: var(--p-surface-overlay);
      border: 1px solid var(--p-content-border-color);
      border-radius: var(--p-border-radius-sm, 4px);
      padding: 6px 10px;
      font-size: 0.75rem;
      line-height: 1.5;
      color: var(--p-text-color);
      white-space: pre;
      box-shadow: var(--p-overlay-popover-shadow, 0 2px 8px rgba(0,0,0,.15));
    }
  `],
  template: `
    <div class="flex-1 min-h-0 relative">
      @if (loading()) {
        <div class="absolute inset-0 flex items-center justify-center text-xs text-surface-500">Loading lineage…</div>
      } @else if (!hasData()) {
        <app-empty-state title="No lineage to show"
                         message="No upstream feed runs or downstream events recorded for this run."
                         icon="inbox"/>
      } @else {
        <div #container class="absolute inset-0"></div>
      }
      <div #tooltip class="dag-tooltip" style="display:none"></div>
    </div>
  `,
})
export class FeedRunLineageDagComponent implements AfterViewInit, OnDestroy {
  private feedService = inject(FeedService);
  private router = inject(Router);

  feedId = input.required<string>();
  run = input<FeedRunListItem | null>(null);

  loading = signal(false);
  lineage = signal<FeedRunLineageResponse | null>(null);

  private container = viewChild<ElementRef<HTMLDivElement>>('container');
  private tooltip = viewChild.required<ElementRef<HTMLDivElement>>('tooltip');
  private resizeObserver?: ResizeObserver;

  hasData = () => {
    const l = this.lineage();
    if (!l) return false;
    return (
      l.upstream_runs.length > 0 ||
      l.downstream_strategy_runs.length > 0 ||
      l.downstream_trades.length > 0
    );
  };

  constructor() {
    effect(() => {
      const r = this.run();
      const fid = this.feedId();
      if (!r || !fid) return;
      this.fetchLineage(fid, r.id);
    });
    effect(() => {
      this.lineage();
      queueMicrotask(() => this.render());
    });
  }

  ngAfterViewInit(): void {
    this.resizeObserver = new ResizeObserver(() => this.render());
    const el = this.container()?.nativeElement;
    if (el) this.resizeObserver.observe(el);
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
  }

  private fetchLineage(feedId: string, runId: string): void {
    this.loading.set(true);
    this.feedService.loadFeedRunLineage(feedId, runId).subscribe({
      next: lineage => {
        this.lineage.set(lineage);
        this.loading.set(false);
      },
      error: () => {
        this.lineage.set(null);
        this.loading.set(false);
      },
    });
  }

  private render(): void {
    const el = this.container()?.nativeElement;
    if (!el) return;
    const tip = this.tooltip().nativeElement;
    d3.select(el).selectAll('svg').remove();

    const lineage = this.lineage();
    const r = this.run();
    if (!lineage || !r) return;

    const router = this.router;
    const layers: DagNode[][] = [
      lineage.upstream_runs.map(u => ({
        id: u.feed_run_id,
        layer: 0,
        label: u.feed_display_name,
        sublabel: u.snapshot_timestamp.replace('T', ' ').slice(0, 19),
        status: u.status,
        color: 'var(--graph-accent-1)',
        routeFn: () => router.navigate(['/feeds', u.feed_id, 'runs', u.feed_run_id]),
      })),
      [
        {
          id: r.id,
          layer: 1,
          label: `Run #${r.id.slice(0, 8)}`,
          sublabel: r.snapshot_timestamp.replace('T', ' ').slice(0, 19),
          status: r.status,
          color: 'var(--info)',
          routeFn: () => {},
        },
      ],
      lineage.downstream_strategy_runs.map(s => ({
        id: s.strategy_run_id,
        layer: 2,
        label: s.strategy_display_name,
        sublabel: s.is_trigger ? 'trigger' : '',
        status: s.status,
        color: 'var(--graph-accent-2)',
        routeFn: () => router.navigate(['/strategies', s.strategy_id, 'runs', s.strategy_run_id]),
      })),
      lineage.downstream_trades.map(t => ({
        id: t.trade_id,
        layer: 3,
        label: `Trade ${t.trade_id.slice(0, 8)}`,
        sublabel: t.status,
        status: t.status,
        color: 'var(--positive)',
        routeFn: () => router.navigate(['/trades', t.trade_id]),
      })),
    ];

    const usedLayers = layers.filter(l => l.length > 0);
    if (usedLayers.length === 0) return;

    const width = el.clientWidth;
    const height = el.clientHeight || 240;
    if (width <= 0) return;

    const margin = { top: 24, right: 32, bottom: 24, left: 32 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const layerXStep = usedLayers.length > 1 ? innerWidth / (usedLayers.length - 1) : 0;
    const nodeWidth = 160;
    const nodeHeight = 48;

    usedLayers.forEach((layer, layerIdx) => {
      const x = margin.left + layerIdx * layerXStep - nodeWidth / 2;
      const yStep = innerHeight / Math.max(1, layer.length);
      layer.forEach((node, nodeIdx) => {
        node.x = Math.max(margin.left, Math.min(width - margin.right - nodeWidth, x));
        node.y = margin.top + nodeIdx * yStep + (yStep - nodeHeight) / 2;
      });
    });

    const svg = d3
      .select(el)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('font-family', 'inherit');

    const allNodes = usedLayers.flat();
    const nodesById = new Map(allNodes.map(n => [n.id, n]));

    const edges: { from: DagNode; to: DagNode }[] = [];
    const thisRun = nodesById.get(r.id);
    if (thisRun) {
      for (const u of lineage.upstream_runs) {
        const from = nodesById.get(u.feed_run_id);
        if (from) edges.push({ from, to: thisRun });
      }
      for (const s of lineage.downstream_strategy_runs) {
        const to = nodesById.get(s.strategy_run_id);
        if (to) edges.push({ from: thisRun, to });
      }
      for (const t of lineage.downstream_trades) {
        const to = nodesById.get(t.trade_id);
        if (!to) continue;
        const triggerStrategyRun = lineage.downstream_strategy_runs.find(
          s => s.strategy_run_id === (t as any).strategy_run_id,
        );
        const from = triggerStrategyRun ? nodesById.get(triggerStrategyRun.strategy_run_id) : thisRun;
        if (from) edges.push({ from, to });
      }
    }

    svg
      .append('g')
      .attr('class', 'edges')
      .selectAll<SVGPathElement, { from: DagNode; to: DagNode }>('path')
      .data(edges)
      .enter()
      .append('path')
      .attr('d', d => {
        const x1 = (d.from.x ?? 0) + nodeWidth;
        const y1 = (d.from.y ?? 0) + nodeHeight / 2;
        const x2 = d.to.x ?? 0;
        const y2 = (d.to.y ?? 0) + nodeHeight / 2;
        const midX = (x1 + x2) / 2;
        return `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`;
      })
      .attr('fill', 'none')
      .attr('stroke', 'var(--edge, rgba(0,0,0,0.2))')
      .attr('stroke-width', 1.5);

    const nodeG = svg
      .append('g')
      .attr('class', 'nodes')
      .selectAll<SVGGElement, DagNode>('g')
      .data(allNodes, d => d.id)
      .enter()
      .append('g')
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .style('cursor', 'pointer')
      .on('mouseover', (event: MouseEvent, d: DagNode) => {
        tip.textContent = `${d.label}\n${d.sublabel ?? ''}\n${d.status}`;
        tip.style.display = 'block';
        tip.style.left = `${event.clientX + 10}px`;
        tip.style.top = `${event.clientY + 10}px`;
      })
      .on('mousemove', (event: MouseEvent) => {
        tip.style.left = `${event.clientX + 10}px`;
        tip.style.top = `${event.clientY + 10}px`;
      })
      .on('mouseleave', () => {
        tip.style.display = 'none';
      })
      .on('click', (_: MouseEvent, d: DagNode) => d.routeFn());

    nodeG
      .append('rect')
      .attr('width', nodeWidth)
      .attr('height', nodeHeight)
      .attr('rx', 6)
      .attr('fill', 'var(--surface)')
      .attr('stroke', d => d.color)
      .attr('stroke-width', 2);

    nodeG
      .append('text')
      .attr('x', 10)
      .attr('y', 18)
      .attr('font-size', '12px')
      .attr('font-weight', 600)
      .attr('fill', 'var(--fg, currentColor)')
      .text(d => d.label.length > 22 ? d.label.slice(0, 22) + '…' : d.label);

    nodeG
      .append('text')
      .attr('x', 10)
      .attr('y', 36)
      .attr('font-size', '10px')
      .attr('fill', 'var(--fg-muted)')
      .text(d => d.sublabel ?? '');
  }
}
