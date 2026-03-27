import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { CHART_COLORS } from './chart-defaults';

@Component({
  selector: 'app-win-loss-chart',
  standalone: true,
  imports: [UIChart],
  template: `
    <div class="h-full w-full min-h-[200px] relative">
      @if (wins() + losses() + breakeven() > 0) {
        <p-chart type="doughnut" [data]="chartData()" [options]="chartOptions"/>
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div class="text-center">
            <span class="text-2xl font-bold text-fg">{{ winRate() }}%</span>
            <span class="block text-xs text-fg-muted">Win Rate</span>
          </div>
        </div>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class WinLossChartComponent {
  wins = input.required<number>();
  losses = input.required<number>();
  breakeven = input.required<number>();

  winRate = computed(() => {
    const total = this.wins() + this.losses();
    if (total === 0) return 0;
    return Math.round((this.wins() / total) * 100);
  });

  chartOptions: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '65%',
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          color: '#a1a1aa',
          padding: 16,
          usePointStyle: true,
          pointStyleWidth: 10,
        },
      },
      tooltip: {
        backgroundColor: '#18181b',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleColor: '#ffffff',
        bodyColor: '#a1a1aa',
        padding: 10,
        cornerRadius: 8,
      },
    },
  };

  chartData = computed<ChartData<'doughnut'>>(() => {
    const data = [];
    const labels = [];
    const colors = [];

    if (this.wins() > 0) {
      data.push(this.wins());
      labels.push('Wins');
      colors.push(CHART_COLORS.positive);
    }
    if (this.losses() > 0) {
      data.push(this.losses());
      labels.push('Losses');
      colors.push(CHART_COLORS.negative);
    }
    if (this.breakeven() > 0) {
      data.push(this.breakeven());
      labels.push('Breakeven');
      colors.push(CHART_COLORS.info);
    }

    return {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderWidth: 0,
        hoverOffset: 4,
      }],
    };
  });
}
