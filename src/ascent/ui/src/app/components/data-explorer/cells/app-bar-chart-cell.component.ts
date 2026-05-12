import { Component, ElementRef, effect, inject, input, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import * as d3 from 'd3';
import { AppChartCanvasComponent, ChartCanvasFrame } from '../../ui/chart-canvas/app-chart-canvas.component';
import { ChartTokensService } from '../../ui/chart-canvas/chart-tokens.service';
import { DataExplorerService } from '../../../services/data-explorer.service';
import { DataExplorerCursorService } from '../cursor.service';
import type { ChartCell } from '../types';

interface BarBucket {
  t: Date;
  values: { color: string; label: string; v: number }[];
}

/** Grouped bar chart over time. Multi-series → one group per bucket, one
 *  bar per series. Forces a sensible default bucket if none specified
 *  (otherwise raw points produce uselessly thin bars at scale). */
@Component({
  selector: 'app-bar-chart-cell',
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
export class AppBarChartCellComponent {
  cell = input.required<ChartCell>();
  table = input.required<string>();
  start = input<string | null>(null);
  end = input<string | null>(null);
  height = input<number>(280);

  private dataService = inject(DataExplorerService);
  private tokens = inject(ChartTokensService);
  private cursorSvc = inject(DataExplorerCursorService);
  private host = inject(ElementRef<HTMLElement>);

  private buckets = signal<BarBucket[]>([]);
  private seriesLabels = signal<string[]>([]);
  private seriesColors = signal<string[]>([]);
  private lastFrame: ChartCanvasFrame | null = null;

  constructor() {
    effect(() => this.fetchAll());
    effect(() => {
      this.cursorSvc.cursor();
      this.draw();
    });
  }

  private fetchAll(): void {
    const c = this.cell();
    const tbl = this.table();
    if (!tbl || c.series.length === 0) {
      this.buckets.set([]);
      return;
    }
    const start = this.start();
    const end = this.end();
    // Bar charts default to day buckets when none specified — raw timestamps
    // produce overlapping bars at most realistic scales.
    const bucket = c.bucket && c.bucket !== 'none' ? c.bucket : 'day';
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
        aggregation: spec.aggregation ?? 'mean',
      }),
    );

    forkJoin(requests).subscribe((responses) => {
      const labels: string[] = [];
      const colors: string[] = [];
      // Merge by timestamp:
      const bucketMap = new Map<number, BarBucket>();
      responses.forEach((r, i) => {
        const color = palette[i % palette.length];
        const label = c.series[i].label?.trim() || `${r.entity_label} · ${r.descriptor_label}`;
        labels.push(label);
        colors.push(color);
        for (const p of r.points) {
          if (p.value == null) continue;
          const ts = new Date(p.timestamp);
          const key = ts.getTime();
          if (!bucketMap.has(key)) bucketMap.set(key, { t: ts, values: [] });
          bucketMap.get(key)!.values.push({ color, label, v: p.value });
        }
      });
      this.seriesLabels.set(labels);
      this.seriesColors.set(colors);
      this.buckets.set(Array.from(bucketMap.values()).sort((a, b) => +a.t - +b.t));
      this.draw();
    });
  }

  private palette(): string[] {
    const t = this.tokens.tokens();
    return [t.graphAccent1, t.graphAccent2, t.graphAccent3, t.graphAccent4, t.graphAccent5];
  }

  onFrame(frame: ChartCanvasFrame): void {
    this.lastFrame = frame;
    this.draw();
  }

  private draw(): void {
    const frame = this.lastFrame;
    if (!frame) return;
    const buckets = this.buckets();
    const tokens = frame.tokens;
    const target = this.host.nativeElement.querySelector('app-chart-canvas svg') as SVGSVGElement | null;
    if (!target) return;
    const sel = d3.select(target);
    sel.selectAll('*').remove();
    if (buckets.length === 0) return;

    const margin = { top: 12, right: 16, bottom: 28, left: 48 };
    const innerW = Math.max(0, frame.width - margin.left - margin.right);
    const innerH = Math.max(0, frame.height - margin.top - margin.bottom);

    const xDomain = buckets.map((b) => b.t.toISOString());
    const xBand = d3.scaleBand<string>().domain(xDomain).range([0, innerW]).padding(0.1);

    const labels = this.seriesLabels();
    const colors = this.seriesColors();
    const innerBand = d3.scaleBand<string>().domain(labels).range([0, xBand.bandwidth()]).padding(0.05);

    const allValues = buckets.flatMap((b) => b.values.map((v) => v.v));
    const yMin = Math.min(0, d3.min(allValues) ?? 0);
    const yMax = Math.max(0, d3.max(allValues) ?? 1);
    const yScale = d3.scaleLinear().domain([yMin, yMax]).nice().range([innerH, 0]);

    const g = sel.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(yScale).ticks(5).tickSize(-innerW).tickFormat(() => '') as any)
      .selectAll('line')
      .attr('stroke', tokens.edge)
      .attr('stroke-opacity', 0.6);
    g.select('.grid .domain').remove();

    // Axes
    const tickFormatter = d3.timeFormat('%b %d');
    const tickEvery = Math.max(1, Math.floor(buckets.length / Math.max(2, Math.floor(innerW / 90))));
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(
        d3
          .axisBottom(xBand)
          .tickValues(xDomain.filter((_, i) => i % tickEvery === 0))
          .tickFormat((v) => tickFormatter(new Date(v as string))) as any,
      )
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5) as any)
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');
    g.selectAll('path.domain, .tick line').attr('stroke', tokens.edge);

    // Bars
    for (const b of buckets) {
      const xb = xBand(b.t.toISOString())!;
      for (const v of b.values) {
        const xi = innerBand(v.label);
        if (xi == null) continue;
        const y0 = yScale(0);
        const y1 = yScale(v.v);
        g.append('rect')
          .attr('x', xb + xi)
          .attr('y', Math.min(y0, y1))
          .attr('width', innerBand.bandwidth())
          .attr('height', Math.abs(y1 - y0))
          .attr('fill', v.color);
      }
    }

    // Cursor (sync, x-axis only)
    const cursorTs = this.cursorSvc.cursor();
    if (cursorTs != null) {
      // Find the closest bucket to the cursor
      let closest: BarBucket | null = null;
      let bestDiff = Infinity;
      for (const b of buckets) {
        const diff = Math.abs(b.t.getTime() - cursorTs);
        if (diff < bestDiff) {
          bestDiff = diff;
          closest = b;
        }
      }
      if (closest) {
        const xb = xBand(closest.t.toISOString());
        if (xb != null) {
          g.append('rect')
            .attr('x', xb)
            .attr('y', 0)
            .attr('width', xBand.bandwidth())
            .attr('height', innerH)
            .attr('fill', tokens.fgFaint)
            .attr('opacity', 0.08)
            .attr('pointer-events', 'none');
        }
      }
    }

    // Hover capture
    g.append('rect')
      .attr('width', innerW)
      .attr('height', innerH)
      .attr('fill', 'transparent')
      .style('cursor', 'crosshair')
      .on('mousemove', (event) => {
        const [mx] = d3.pointer(event);
        // Find which bucket contains mx
        let nearest: BarBucket | null = null;
        let bestDiff = Infinity;
        for (const b of buckets) {
          const xb = (xBand(b.t.toISOString()) ?? 0) + xBand.bandwidth() / 2;
          const diff = Math.abs(xb - mx);
          if (diff < bestDiff) {
            bestDiff = diff;
            nearest = b;
          }
        }
        if (nearest) this.cursorSvc.set(nearest.t.getTime());
      })
      .on('mouseleave', () => this.cursorSvc.clear());
  }
}
