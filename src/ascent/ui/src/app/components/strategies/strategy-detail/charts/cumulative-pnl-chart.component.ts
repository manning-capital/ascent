import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { DARK_THEME, CHART_COLORS } from './chart-defaults';

export interface CumulativePnlPoint {
  date: string;
  value: number;
  symbol: string;
}

@Component({
  selector: 'app-cumulative-pnl-chart',
  standalone: true,
  imports: [UIChart],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (data().length > 0) {
        <p-chart type="line" [data]="chartData()" [options]="chartOptions"/>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class CumulativePnlChartComponent {
  data = input.required<CumulativePnlPoint[]>();

  chartOptions: ChartOptions<'line'> = {
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
    const points = this.data();
    return {
      labels: points.map(p => new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [{
        data: points.map(p => p.value),
        borderColor: CHART_COLORS.positive,
        backgroundColor: CHART_COLORS.positiveFill,
        fill: true,
        tension: 0.3,
        pointRadius: points.length > 50 ? 0 : 3,
        pointHoverRadius: 5,
        pointBackgroundColor: CHART_COLORS.positive,
        borderWidth: 2,
      }],
    };
  });
}
