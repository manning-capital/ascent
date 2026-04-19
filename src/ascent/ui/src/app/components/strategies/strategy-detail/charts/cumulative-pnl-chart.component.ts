import { Component, computed, input, model } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { DARK_THEME, CHART_COLORS } from './chart-defaults';

export interface CumulativePnlPoint {
  date: string;
  value: number;
  symbol: string;
}

export type Lookback = '1d' | '7d' | '30d' | 'all';

export const LOOKBACK_OPTIONS = [
  { label: '1D', value: '1d' as Lookback },
  { label: '7D', value: '7d' as Lookback },
  { label: '30D', value: '30d' as Lookback },
  { label: 'All', value: 'all' as Lookback },
];

const LOOKBACK_MS: Record<Lookback, number | null> = {
  '1d': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
  'all': null,
};

@Component({
  selector: 'app-cumulative-pnl-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (filteredData().length > 0) {
        <p-chart type="line" [data]="chartData()" [options]="chartOptions" [style]="{'width': '100%', 'height': '100%'}"/>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">
          No closed trades in selected window
        </div>
      }
    </div>
  `,
})
export class CumulativePnlChartComponent {
  data = input.required<CumulativePnlPoint[]>();
  lookback = model<Lookback>('all');

  filteredData = computed<CumulativePnlPoint[]>(() => {
    const points = this.data();
    const window = LOOKBACK_MS[this.lookback()];
    if (window === null) return points;
    const cutoff = Date.now() - window;
    return points.filter(p => new Date(p.date).getTime() >= cutoff);
  });

  chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
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
      },
    },
    scales: {
      x: {
        ticks: { color: DARK_THEME.tickColor, maxTicksLimit: 10 },
        grid: { color: DARK_THEME.gridColor },
      },
      y: {
        ticks: {
          color: DARK_THEME.tickColor,
          callback: (value) => `$${value}`,
        },
        grid: { color: DARK_THEME.gridColor },
      },
    },
  };

  chartData = computed<ChartData<'line'>>(() => {
    const points = this.filteredData();
    return {
      labels: points.map(p => new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [{
        data: points.map(p => p.value),
        borderColor: CHART_COLORS.positive,
        backgroundColor: CHART_COLORS.positiveFill,
        fill: true,
        tension: 0,
        pointRadius: points.length > 50 ? 0 : 3,
        pointHoverRadius: 5,
        pointBackgroundColor: CHART_COLORS.positive,
        borderWidth: 2,
      }],
    };
  });
}
