import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { DARK_THEME, CHART_COLORS } from './chart-defaults';

@Component({
  selector: 'app-pnl-distribution-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (pnls().length > 0) {
        <p-chart type="bar" [data]="chartData()" [options]="chartOptions" [style]="{'width': '100%', 'height': '100%'}"/>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class PnlDistributionChartComponent {
  pnls = input.required<number[]>();

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

  chartOptions: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: DARK_THEME.tooltipBg,
        borderColor: DARK_THEME.tooltipBorder,
        borderWidth: 1,
        titleColor: DARK_THEME.tooltipTitle,
        bodyColor: DARK_THEME.tooltipBody,
        padding: 10,
        cornerRadius: 8,
        callbacks: {
          title: (items) => {
            const val = items[0]?.label ?? '';
            return `PnL: $${val}`;
          },
          label: (item) => `Count: ${item.raw}`,
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: DARK_THEME.tickColor,
          maxTicksLimit: 10,
        },
        grid: { color: DARK_THEME.gridColor },
        title: { display: true, text: 'PnL ($)', color: DARK_THEME.labelColor },
      },
      y: {
        ticks: { color: DARK_THEME.tickColor },
        grid: { color: DARK_THEME.gridColor },
        title: { display: true, text: 'Count', color: DARK_THEME.labelColor },
      },
    },
  };

  chartData = computed<ChartData<'bar'>>(() => {
    const { centers, counts } = this.histogram();
    return {
      labels: centers.map(c => `$${c.toFixed(0)}`),
      datasets: [{
        data: counts,
        backgroundColor: centers.map(c => c >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)'),
        borderRadius: 2,
        barPercentage: 1.0,
        categoryPercentage: 1.0,
      }],
    };
  });
}
