import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  input,
  output,
  viewChild,
} from '@angular/core';
import * as d3 from 'd3';

export interface TimelineRun {
  id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  snapshot_timestamp: string;
}

@Component({
  selector: 'app-feed-activity-timeline',
  standalone: true,
  styles: [`
    :host { display: block; position: relative; }
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
      white-space: nowrap;
      box-shadow: var(--p-overlay-popover-shadow, 0 2px 8px rgba(0,0,0,.15));
    }
  `],
  template: `
    <div #container class="w-full text-surface-500" [style.height.px]="height"></div>
    <div #tooltip class="tl-tooltip" style="display:none"></div>
  `,
})
export class FeedActivityTimelineComponent implements AfterViewInit, OnDestroy {
  runs = input.required<TimelineRun[]>();
  runClick = output<string>();

  private container = viewChild.required<ElementRef<HTMLDivElement>>('container');
  private tooltip = viewChild.required<ElementRef<HTMLDivElement>>('tooltip');
  private resizeObserver?: ResizeObserver;
  readonly height = 80;

  constructor() {
    effect(() => {
      this.runs();
      queueMicrotask(() => this.render());
    });
  }

  ngAfterViewInit(): void {
    this.render();
    this.resizeObserver = new ResizeObserver(() => this.render());
    this.resizeObserver.observe(this.container().nativeElement);
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
  }

  private render(): void {
    const el = this.container().nativeElement;
    const tip = this.tooltip().nativeElement;
    d3.select(el).selectAll('svg').remove();

    const runs = this.runs();
    if (!runs.length) return;

    const width = el.clientWidth;
    if (width <= 0) return;

    const margin = { top: 6, right: 12, bottom: 22, left: 12 };
    const innerWidth = width - margin.left - margin.right;
    const laneHeight = 32;

    const now = new Date();
    const times = runs.flatMap(r => [
      new Date(r.started_at),
      r.completed_at ? new Date(r.completed_at) : now,
    ]);
    const minTime = d3.min(times)!;
    const maxTime = d3.max(times)!;
    const span = maxTime.getTime() - minTime.getTime();
    const pad = Math.max(span * 0.02, 30_000);
    const domainStart = new Date(minTime.getTime() - pad);
    const domainEnd = new Date(Math.max(maxTime.getTime() + pad, now.getTime()));

    const xScale = d3.scaleTime().domain([domainStart, domainEnd]).range([0, innerWidth]);

    const svg = d3
      .select(el)
      .append('svg')
      .attr('width', width)
      .attr('height', this.height);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('rect')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerWidth)
      .attr('height', laneHeight)
      .attr('rx', 3)
      .attr('fill', 'currentColor')
      .attr('opacity', 0.06);

    g.selectAll('rect.run')
      .data(runs)
      .enter()
      .append('rect')
      .attr('class', 'run')
      .attr('x', d => xScale(new Date(d.started_at)))
      .attr('y', 0)
      .attr('width', d => {
        const start = xScale(new Date(d.started_at));
        const end = xScale(d.completed_at ? new Date(d.completed_at) : now);
        return Math.max(3, end - start);
      })
      .attr('height', laneHeight)
      .attr('rx', 2)
      .attr('fill', d => this.fillForStatus(d.status))
      .attr('opacity', 0.85)
      .style('cursor', 'pointer')
      .on('mouseenter', (_event, d) => {
        tip.innerHTML = this.tooltipHtml(d);
        tip.style.display = 'block';
      })
      .on('mousemove', (event: MouseEvent) => {
        const offset = 12;
        const tipW = tip.offsetWidth;
        const tipH = tip.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        let x = event.clientX + offset;
        let y = event.clientY - tipH - offset;
        if (x + tipW > vw) x = event.clientX - tipW - offset;
        if (y < 0) y = event.clientY + offset;
        tip.style.left = `${x}px`;
        tip.style.top = `${y}px`;
      })
      .on('mouseleave', function () {
        tip.style.display = 'none';
        d3.select(this).attr('opacity', 0.85);
      })
      .on('click', (_event, d) => this.runClick.emit(d.id));

    const axis = d3.axisBottom(xScale).ticks(Math.max(3, Math.floor(innerWidth / 110))).tickSize(4);
    const axisG = g
      .append('g')
      .attr('transform', `translate(0,${laneHeight + 6})`)
      .call(axis as any);
    axisG.select('.domain').remove();
    axisG.selectAll('text').attr('font-size', '10px').attr('fill', 'currentColor');
    axisG.selectAll('line').attr('stroke', 'currentColor').attr('opacity', 0.3);
  }

  private tooltipHtml(run: TimelineRun): string {
    const start = new Date(run.started_at);
    const end = run.completed_at ? new Date(run.completed_at) : null;
    const duration = end ? this.formatDuration(end.getTime() - start.getTime()) : 'in progress';
    const snapshot = new Date(run.snapshot_timestamp).toLocaleString();
    const statusColor = this.fillForStatus(run.status);
    return [
      `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">`,
      `  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${statusColor}"></span>`,
      `  <strong>${run.status}</strong>`,
      `</div>`,
      `<div>Started: ${start.toLocaleString()} <span style="opacity:.6">(${duration})</span></div>`,
      `<div style="margin-top:2px">Snapshot: <strong>${snapshot}</strong></div>`,
    ].join('');
  }

  private fillForStatus(status: string): string {
    const styles = getComputedStyle(document.documentElement);
    const read = (name: string) => styles.getPropertyValue(name).trim();
    switch (status) {
      case 'COMPLETED': return read('--positive');
      case 'FAILED': return read('--negative');
      case 'RUNNING': return read('--warning');
      default: return read('--fg-faint');
    }
  }

  private formatDuration(ms: number): string {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
    if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
    return `${(ms / 3_600_000).toFixed(1)}h`;
  }
}
