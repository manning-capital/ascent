import { Component, ElementRef, effect, inject, input, signal } from '@angular/core';
import * as d3 from 'd3';
import { AppChartCanvasComponent, ChartCanvasFrame } from '../../ui/chart-canvas/app-chart-canvas.component';
import { ChartTokensService } from '../../ui/chart-canvas/chart-tokens.service';
import { DataExplorerService } from '../../../services/data-explorer.service';
import type { ChartCell } from '../types';

/** Histogram of a single descriptor's values for one entity. Bin count
 *  defaults to ``ceil(sqrt(n))`` (with a floor of 5 and ceiling of 60). */
@Component({
  selector: 'app-histogram-cell',
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
export class AppHistogramCellComponent {
  cell = input.required<ChartCell>();
  table = input.required<string>();
  start = input<string | null>(null);
  end = input<string | null>(null);
  height = input<number>(280);

  private dataService = inject(DataExplorerService);
  private tokens = inject(ChartTokensService);
  private host = inject(ElementRef<HTMLElement>);

  private values = signal<number[]>([]);
  private label = signal<string>('');
  private lastFrame: ChartCanvasFrame | null = null;

  constructor() {
    effect(() => this.fetchAll());
  }

  private fetchAll(): void {
    const c = this.cell();
    const tbl = this.table();
    if (!tbl || c.series.length === 0) {
      this.values.set([]);
      return;
    }
    const spec = c.series[0];
    this.dataService
      .fetchSeries({
        table: tbl,
        entityId: spec.entityId,
        descriptorId: spec.descriptorId,
        periodId: spec.periodId,
        start: this.start(),
        end: this.end(),
      })
      .subscribe((res) => {
        this.values.set(res.points.filter((p) => p.value != null).map((p) => p.value as number));
        this.label.set(`${res.entity_label} · ${res.descriptor_label}`);
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
    const values = this.values();
    const tokens = frame.tokens;
    const target = this.host.nativeElement.querySelector('app-chart-canvas svg') as SVGSVGElement | null;
    if (!target) return;
    const sel = d3.select(target);
    sel.selectAll('*').remove();
    if (values.length === 0) return;

    const margin = { top: 12, right: 16, bottom: 36, left: 48 };
    const innerW = Math.max(0, frame.width - margin.left - margin.right);
    const innerH = Math.max(0, frame.height - margin.top - margin.bottom);

    const extent = d3.extent(values) as [number, number];
    const xScale = d3.scaleLinear().domain(extent).nice().range([0, innerW]);
    const binCount = Math.min(60, Math.max(5, Math.ceil(Math.sqrt(values.length))));
    const bins = d3.bin().domain(xScale.domain() as [number, number]).thresholds(binCount)(values);
    const yMax = d3.max(bins, (b) => b.length) ?? 1;
    const yScale = d3.scaleLinear().domain([0, yMax]).nice().range([innerH, 0]);

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

    g.append('text')
      .attr('x', innerW / 2)
      .attr('y', innerH + 28)
      .attr('text-anchor', 'middle')
      .attr('fill', tokens.fgMuted)
      .style('font-size', '10px')
      .text(this.label());

    g.append('g')
      .selectAll('rect')
      .data(bins)
      .enter()
      .append('rect')
      .attr('x', (d) => xScale(d.x0 ?? 0) + 1)
      .attr('y', (d) => yScale(d.length))
      .attr('width', (d) => Math.max(0, xScale(d.x1 ?? 0) - xScale(d.x0 ?? 0) - 1))
      .attr('height', (d) => innerH - yScale(d.length))
      .attr('fill', tokens.graphAccent1);
  }
}
