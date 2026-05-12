import { Component, ElementRef, effect, inject, input, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import * as d3 from 'd3';
import { AppChartCanvasComponent, ChartCanvasFrame } from '../../ui/chart-canvas/app-chart-canvas.component';
import { ChartTokensService } from '../../ui/chart-canvas/chart-tokens.service';
import { DataExplorerService } from '../../../services/data-explorer.service';
import type { ChartCell } from '../types';

interface ScatterPoint {
  x: number;
  y: number;
  t: Date;
}

/** Scatter plot. Requires exactly 2 series — series[0] becomes the x-axis,
 *  series[1] the y-axis. Points are joined by timestamp; mismatched points
 *  are dropped. */
@Component({
  selector: 'app-scatter-chart-cell',
  standalone: true,
  imports: [AppChartCanvasComponent],
  template: `
    @if (cell().series.length < 2) {
      <div class="flex-1 min-h-0 flex items-center justify-center text-fg-faint text-xs p-6">
        Scatter requires two series (x-axis, then y-axis).
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
export class AppScatterChartCellComponent {
  cell = input.required<ChartCell>();
  table = input.required<string>();
  start = input<string | null>(null);
  end = input<string | null>(null);
  height = input<number>(280);

  private dataService = inject(DataExplorerService);
  private tokens = inject(ChartTokensService);
  private host = inject(ElementRef<HTMLElement>);

  private points = signal<ScatterPoint[]>([]);
  private xLabel = signal<string>('');
  private yLabel = signal<string>('');
  private lastFrame: ChartCanvasFrame | null = null;

  constructor() {
    effect(() => this.fetchAll());
  }

  private fetchAll(): void {
    const c = this.cell();
    const tbl = this.table();
    if (!tbl || c.series.length < 2) {
      this.points.set([]);
      return;
    }
    const start = this.start();
    const end = this.end();
    const [xSpec, ySpec] = c.series;

    forkJoin([
      this.dataService.fetchSeries({
        table: tbl,
        entityId: xSpec.entityId,
        descriptorId: xSpec.descriptorId,
        periodId: xSpec.periodId,
        start,
        end,
      }),
      this.dataService.fetchSeries({
        table: tbl,
        entityId: ySpec.entityId,
        descriptorId: ySpec.descriptorId,
        periodId: ySpec.periodId,
        start,
        end,
      }),
    ]).subscribe(([xRes, yRes]) => {
      // Inner-join by timestamp (millisecond)
      const yMap = new Map<number, number>();
      for (const p of yRes.points) {
        if (p.value != null) yMap.set(new Date(p.timestamp).getTime(), p.value);
      }
      const joined: ScatterPoint[] = [];
      for (const p of xRes.points) {
        if (p.value == null) continue;
        const key = new Date(p.timestamp).getTime();
        const yv = yMap.get(key);
        if (yv == null) continue;
        joined.push({ x: p.value, y: yv, t: new Date(p.timestamp) });
      }
      this.points.set(joined);
      this.xLabel.set(`${xRes.entity_label} · ${xRes.descriptor_label}`);
      this.yLabel.set(`${yRes.entity_label} · ${yRes.descriptor_label}`);
      this.draw();
    });
  }

  onFrame(frame: ChartCanvasFrame): void {
    this.lastFrame = frame;
    this.draw();
  }

  private draw(): void {
    const frame = this.lastFrame;
    if (!frame) return;
    const points = this.points();
    const tokens = frame.tokens;
    const target = this.host.nativeElement.querySelector('app-chart-canvas svg') as SVGSVGElement | null;
    if (!target) return;
    const sel = d3.select(target);
    sel.selectAll('*').remove();
    if (points.length === 0) return;

    const margin = { top: 12, right: 16, bottom: 36, left: 56 };
    const innerW = Math.max(0, frame.width - margin.left - margin.right);
    const innerH = Math.max(0, frame.height - margin.top - margin.bottom);

    const xDomain = d3.extent(points, (p) => p.x) as [number, number];
    const yDomain = d3.extent(points, (p) => p.y) as [number, number];
    const xScale = d3.scaleLinear().domain(xDomain).nice().range([0, innerW]);
    const yScale = d3.scaleLinear().domain(yDomain).nice().range([innerH, 0]);

    const g = sel.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(yScale).ticks(5).tickSize(-innerW).tickFormat(() => '') as any)
      .selectAll('line')
      .attr('stroke', tokens.edge)
      .attr('stroke-opacity', 0.6);
    g.select('.grid .domain').remove();

    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(Math.max(2, Math.floor(innerW / 90))) as any)
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5) as any)
      .selectAll('text')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px');
    g.selectAll('path.domain, .tick line').attr('stroke', tokens.edge);

    // Axis labels
    g.append('text')
      .attr('x', innerW / 2)
      .attr('y', innerH + 28)
      .attr('text-anchor', 'middle')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px')
      .text(this.xLabel());
    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerH / 2)
      .attr('y', -42)
      .attr('text-anchor', 'middle')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px')
      .text(this.yLabel());

    g.append('g')
      .selectAll('circle')
      .data(points)
      .enter()
      .append('circle')
      .attr('cx', (d) => xScale(d.x))
      .attr('cy', (d) => yScale(d.y))
      .attr('r', 2.5)
      .attr('fill', tokens.graphAccent1)
      .attr('opacity', 0.75);
  }
}
