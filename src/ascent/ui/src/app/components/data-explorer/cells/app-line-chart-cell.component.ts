import { Component, ElementRef, effect, inject, input, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import * as d3 from 'd3';
import { AppChartCanvasComponent, ChartCanvasFrame } from '../../ui/chart-canvas/app-chart-canvas.component';
import { ChartTokensService } from '../../ui/chart-canvas/chart-tokens.service';
import { DataExplorerService } from '../../../services/data-explorer.service';
import { DataExplorerCursorService } from '../cursor.service';
import type { Bucket, ChartCell, SeriesSpec } from '../types';

interface LinePoint {
  t: Date;
  v: number;
}

interface LineSeriesRendered {
  id: string;
  color: string;
  label: string;
  axis: 'left' | 'right';
  points: LinePoint[];
}

/** Multi-series time-series line chart. Optional dual y-axis (per-series
 *  ``axis: 'left' | 'right'``). Publishes hovered timestamp to the cursor
 *  service and renders the synchronized cursor when other cells publish. */
@Component({
  selector: 'app-line-chart-cell',
  standalone: true,
  imports: [AppChartCanvasComponent],
  template: `
    @if (cell().series.length === 0) {
      <div class="flex-1 min-h-0 flex items-center justify-center text-fg-faint text-xs p-6">
        Add a series to render.
      </div>
    } @else {
      <div class="flex-1 min-h-0 p-2" style="min-height: 240px;">
        <app-chart-canvas
          [fixedHeight]="height()"
          (frame)="onFrame($event)"
        />
      </div>
    }
  `,
})
export class AppLineChartCellComponent {
  cell = input.required<ChartCell>();
  table = input.required<string>();
  start = input<string | null>(null);
  end = input<string | null>(null);

  height = input<number>(280);

  private dataService = inject(DataExplorerService);
  private tokens = inject(ChartTokensService);
  private cursorSvc = inject(DataExplorerCursorService);
  private host = inject(ElementRef<HTMLElement>);

  private rendered = signal<LineSeriesRendered[]>([]);
  private lastFrame: ChartCanvasFrame | null = null;

  constructor() {
    effect(() => this.fetchAll());
    // Re-render when external cursor moves
    effect(() => {
      this.cursorSvc.cursor();
      this.draw();
    });
  }

  // ─── Data fetch ───────────────────────────────────────────
  private fetchAll(): void {
    const c = this.cell();
    const tbl = this.table();
    if (!tbl || c.series.length === 0) {
      this.rendered.set([]);
      return;
    }
    const start = this.start();
    const end = this.end();
    const bucket = c.bucket ?? 'none';
    const palette = this.palette();

    const requests = c.series.map((spec) =>
      this.dataService.fetchSeries({
        table: tbl,
        entityId: spec.entityId,
        descriptorId: spec.descriptorId,
        periodId: spec.periodId,
        start,
        end,
        bucket,
        aggregation: spec.aggregation ?? (bucket === 'none' ? 'none' : 'mean'),
      }),
    );

    forkJoin(requests).subscribe((responses) => {
      const out: LineSeriesRendered[] = c.series.map((spec, i) => {
        const r = responses[i];
        const points = r.points
          .filter((p) => p.value != null)
          .map((p) => ({ t: new Date(p.timestamp), v: p.value as number }));
        return {
          id: spec.id,
          color: palette[i % palette.length],
          label: spec.label?.trim() || `${r.entity_label} · ${r.descriptor_label}`,
          axis: spec.axis ?? 'left',
          points,
        };
      });
      this.rendered.set(out);
      this.draw();
    });
  }

  private palette(): string[] {
    const t = this.tokens.tokens();
    return [t.graphAccent1, t.graphAccent2, t.graphAccent3, t.graphAccent4, t.graphAccent5];
  }

  // ─── Render ───────────────────────────────────────────────
  onFrame(frame: ChartCanvasFrame): void {
    this.lastFrame = frame;
    this.draw();
  }

  private draw(): void {
    const frame = this.lastFrame;
    if (!frame) return;
    const series = this.rendered();
    const tokens = frame.tokens;

    // Scope the SVG lookup to this component's host element so multiple line
    // cells on the same page each draw into their own canvas.
    const target = this.host.nativeElement.querySelector(
      'app-chart-canvas svg',
    ) as SVGSVGElement | null;
    if (!target) return;

    const sel = d3.select(target);
    sel.selectAll('*').remove();

    if (series.length === 0) return;

    const margin = { top: 12, right: 40, bottom: 28, left: 48 };
    const innerW = Math.max(0, frame.width - margin.left - margin.right);
    const innerH = Math.max(0, frame.height - margin.top - margin.bottom);

    const allPoints = series.flatMap((s) => s.points);
    if (allPoints.length === 0) return;

    const xExtent = d3.extent(allPoints, (p) => p.t) as [Date, Date];
    const xScale = d3.scaleTime().domain(xExtent).range([0, innerW]);

    const leftSeries = series.filter((s) => s.axis === 'left');
    const rightSeries = series.filter((s) => s.axis === 'right');

    const yLeftDomain = d3.extent(leftSeries.flatMap((s) => s.points).map((p) => p.v)) as [number, number];
    const yRightDomain = d3.extent(rightSeries.flatMap((s) => s.points).map((p) => p.v)) as [number, number];
    const yLeft = d3.scaleLinear().domain(yLeftDomain[0] != null ? yLeftDomain : [0, 1]).nice().range([innerH, 0]);
    const yRight = rightSeries.length > 0
      ? d3.scaleLinear().domain(yRightDomain[0] != null ? yRightDomain : [0, 1]).nice().range([innerH, 0])
      : null;

    const g = sel.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid lines (horizontal)
    g.append('g')
      .attr('class', 'grid')
      .call(
        d3.axisLeft(yLeft).ticks(5).tickSize(-innerW).tickFormat(() => '') as any,
      )
      .selectAll('line')
      .attr('stroke', tokens.edge)
      .attr('stroke-opacity', 0.6);
    g.select('.grid .domain').remove();

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(Math.max(2, Math.floor(innerW / 90))) as any)
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');
    g.selectAll('path.domain, .tick line').attr('stroke', tokens.edge);

    // Left Y axis
    g.append('g')
      .call(d3.axisLeft(yLeft).ticks(5) as any)
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');

    // Right Y axis (if present)
    if (yRight) {
      g.append('g')
        .attr('transform', `translate(${innerW},0)`)
        .call(d3.axisRight(yRight).ticks(5) as any)
        .selectAll('text')
        .attr('fill', tokens.fgMuted)
        .style('font-size', '10px');
    }

    // Series lines
    const lineGen = (yScale: d3.ScaleLinear<number, number>) =>
      d3
        .line<LinePoint>()
        .x((p) => xScale(p.t))
        .y((p) => yScale(p.v))
        .curve(d3.curveMonotoneX);

    for (const s of series) {
      const yScale = s.axis === 'right' && yRight ? yRight : yLeft;
      g.append('path')
        .datum(s.points)
        .attr('fill', 'none')
        .attr('stroke', s.color)
        .attr('stroke-width', 1.5)
        .attr('d', lineGen(yScale)(s.points) ?? '');
    }

    // Synchronized cursor
    const cursorTs = this.cursorSvc.cursor();
    if (cursorTs != null) {
      const cx = xScale(new Date(cursorTs));
      if (cx >= 0 && cx <= innerW) {
        g.append('line')
          .attr('class', 'sync-cursor')
          .attr('x1', cx)
          .attr('x2', cx)
          .attr('y1', 0)
          .attr('y2', innerH)
          .attr('stroke', tokens.fgFaint)
          .attr('stroke-dasharray', '2,2')
          .attr('stroke-width', 1)
          .attr('pointer-events', 'none');
      }
    }

    // Mouse capture rect for hover
    g.append('rect')
      .attr('width', innerW)
      .attr('height', innerH)
      .attr('fill', 'transparent')
      .style('cursor', 'crosshair')
      .on('mousemove', (event) => {
        const [mx] = d3.pointer(event);
        const t = xScale.invert(mx);
        this.cursorSvc.set(t.getTime());
      })
      .on('mouseleave', () => this.cursorSvc.clear());
  }

}
