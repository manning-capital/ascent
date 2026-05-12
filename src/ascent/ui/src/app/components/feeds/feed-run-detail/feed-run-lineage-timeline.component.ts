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

interface LaneEvent {
  id: string;
  routeFn: () => void;
  timestamp: Date;
  status: string;
  label: string;
  tooltip: string;
}

@Component({
  selector: 'app-feed-run-lineage-timeline',
  standalone: true,
  imports: [AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; height: 100%; }
    .tl-tooltip {
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
      <div #tooltip class="tl-tooltip" style="display:none"></div>
    </div>
  `,
})
export class FeedRunLineageTimelineComponent implements AfterViewInit, OnDestroy {
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

    const width = el.clientWidth;
    const height = el.clientHeight || 240;
    if (width <= 0) return;

    const router = this.router;

    const lanes: { name: string; color: string; events: LaneEvent[] }[] = [
      {
        name: 'Upstream feeds',
        color: 'var(--graph-accent-1)',
        events: lineage.upstream_runs.map(u => ({
          id: u.feed_run_id,
          routeFn: () => router.navigate(['/feeds', u.feed_id, 'runs', u.feed_run_id]),
          timestamp: new Date(u.snapshot_timestamp),
          status: u.status,
          label: u.feed_display_name,
          tooltip: `${u.feed_display_name}\n${u.snapshot_timestamp}\n${u.status}`,
        })),
      },
      {
        name: 'This run',
        color: 'var(--info)',
        events: [
          {
            id: r.id,
            routeFn: () => {},
            timestamp: new Date(r.snapshot_timestamp),
            status: r.status,
            label: `Run #${r.id.slice(0, 8)}`,
            tooltip: `Run #${r.id.slice(0, 8)}\n${r.snapshot_timestamp}\n${r.status}`,
          },
        ],
      },
      {
        name: 'Downstream trades',
        color: 'var(--positive)',
        events: lineage.downstream_trades.map(t => ({
          id: t.trade_id,
          routeFn: () => router.navigate(['/trades', t.trade_id]),
          timestamp: new Date(t.created_at),
          status: t.status,
          label: t.trade_id.slice(0, 8),
          tooltip: `Trade ${t.trade_id.slice(0, 8)}\n${t.created_at}\n${t.status}`,
        })),
      },
    ];

    const allTimestamps: Date[] = [];
    for (const lane of lanes) {
      for (const ev of lane.events) allTimestamps.push(ev.timestamp);
    }
    if (allTimestamps.length === 0) return;

    const minTime = d3.min(allTimestamps) ?? new Date();
    const maxTime = d3.max(allTimestamps) ?? new Date();
    const padMs = Math.max(60_000, (maxTime.getTime() - minTime.getTime()) * 0.05);
    const xScale = d3
      .scaleTime()
      .domain([new Date(minTime.getTime() - padMs), new Date(maxTime.getTime() + padMs)])
      .range([180, width - 16]);

    const laneHeight = (height - 24) / lanes.length;

    const svg = d3
      .select(el)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('font-family', 'inherit')
      .style('font-size', '11px');

    const xAxis = d3.axisBottom(xScale).ticks(Math.max(3, Math.floor(width / 140)));
    svg
      .append('g')
      .attr('transform', `translate(0, ${height - 22})`)
      .attr('color', 'var(--fg-faint)')
      .call(xAxis);

    const guideX = xScale(new Date(r.snapshot_timestamp));
    svg
      .append('line')
      .attr('x1', guideX)
      .attr('x2', guideX)
      .attr('y1', 6)
      .attr('y2', height - 22)
      .attr('stroke', 'var(--info)')
      .attr('stroke-dasharray', '3,3')
      .attr('stroke-width', 1)
      .attr('opacity', 0.5);

    lanes.forEach((lane, idx) => {
      const yTop = 6 + idx * laneHeight;
      const yMid = yTop + laneHeight / 2;

      svg
        .append('text')
        .attr('x', 12)
        .attr('y', yMid + 4)
        .attr('fill', 'var(--fg-muted)')
        .attr('font-weight', 500)
        .text(lane.name);

      svg
        .append('line')
        .attr('x1', 180)
        .attr('x2', width - 16)
        .attr('y1', yMid)
        .attr('y2', yMid)
        .attr('stroke', 'var(--edge, rgba(0,0,0,0.1))')
        .attr('stroke-width', 1);

      const g = svg.append('g').attr('class', `lane-${idx}`);
      const sel = g.selectAll<SVGCircleElement, LaneEvent>('circle').data(lane.events, d => d.id);
      sel
        .enter()
        .append('circle')
        .attr('cx', d => xScale(d.timestamp))
        .attr('cy', yMid)
        .attr('r', 6)
        .attr('fill', lane.color)
        .attr('stroke', 'var(--surface)')
        .attr('stroke-width', 1.5)
        .style('cursor', 'pointer')
        .on('mouseover', (event: MouseEvent, d: LaneEvent) => {
          tip.textContent = d.tooltip;
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
        .on('click', (_: MouseEvent, d: LaneEvent) => d.routeFn());
    });
  }
}
