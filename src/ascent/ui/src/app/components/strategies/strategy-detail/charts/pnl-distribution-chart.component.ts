import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { useChartTheme, withAlpha, formatPnlTick } from './chart-defaults';

@Component({
  selector: 'app-pnl-distribution-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full">
      @if (pnls().length > 0) {
        <p-chart type="bar" [data]="chartData()" [options]="chartOptions()" [style]="{'width': '100%', 'height': '100%'}" />
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class PnlDistributionChartComponent {
  pnls = input.required<number[]>();

  private theme = useChartTheme();

  private histogram = computed(() => {
    const values = this.pnls();
    if (values.length === 0) return { centers: [], counts: [], width: 0 };

    const min = Math.min(...values);
    const max = Math.max(...values);
    const nBins = Math.min(30, Math.max(8, Math.floor(values.length / 4)));
    const width = (max - min) / nBins || 1;
    const counts = new Array(nBins).fill(0);

    for (const v of values) {
      let idx = Math.floor((v - min) / width);
      if (idx >= nBins) idx = nBins - 1;
      counts[idx]++;
    }

    const centers = counts.map((_, i) => min + (i + 0.5) * width);
    return { centers, counts, width };
  });

  chartOptions = computed<ChartOptions<'bar'>>(() => {
    const t = this.theme();
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          borderWidth: 1,
          titleColor: t.tooltipTitle,
          bodyColor: t.tooltipBody,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            title: (items) => {
              const idx = items[0]?.dataIndex ?? 0;
              const center = this.histogram().centers[idx];
              return center != null ? `PnL: ${formatPnlTick(center)}` : '';
            },
            label: (item) => `Count: ${item.raw}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: t.tickColor,
            maxTicksLimit: 6,
            font: { size: 10 },
          },
          grid: { color: t.gridColor },
        },
        y: {
          ticks: {
            color: t.tickColor,
            maxTicksLimit: 5,
            font: { size: 10 },
          },
          grid: { color: t.gridColor },
        },
      },
      layout: {
        padding: { top: 4, right: 4 },
      },
    };
  });

  chartData = computed<ChartData<'bar'>>(() => {
    const t = this.theme();
    const { centers, counts } = this.histogram();
    return {
      labels: centers.map((c) => formatPnlTick(c)),
      datasets: [{
        data: counts,
        backgroundColor: centers.map((c) => withAlpha(c >= 0 ? t.positive : t.negative, 0.7)),
        borderRadius: 2,
        barPercentage: 1.0,
        categoryPercentage: 1.0,
      }],
    };
  });
}
