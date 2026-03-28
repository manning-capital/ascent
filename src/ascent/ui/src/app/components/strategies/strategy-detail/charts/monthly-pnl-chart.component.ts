import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { DARK_THEME, CHART_COLORS } from './chart-defaults';

export interface MonthlyPnlPoint {
  month: string;
  pnl: number;
}

@Component({
  selector: 'app-monthly-pnl-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (data().length > 0) {
        <p-chart type="bar" [data]="chartData()" [options]="chartOptions" [style]="{'width': '100%', 'height': '100%'}"/>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class MonthlyPnlChartComponent {
  data = input.required<MonthlyPnlPoint[]>();

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
          label: (item) => {
            const val = item.raw as number;
            return `P&L: $${val.toFixed(2)}`;
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: DARK_THEME.tickColor },
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

  chartData = computed<ChartData<'bar'>>(() => {
    const points = this.data();
    const pnls = points.map(p => p.pnl);
    return {
      labels: points.map(p => p.month),
      datasets: [{
        data: pnls,
        backgroundColor: pnls.map(v => v >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative),
        borderRadius: 4,
        maxBarThickness: 50,
      }],
    };
  });
}
