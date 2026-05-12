import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { useChartTheme } from './chart-defaults';

@Component({
  selector: 'app-win-loss-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full relative">
      @if (wins() + losses() + breakeven() > 0) {
        <p-chart type="doughnut" [data]="chartData()" [options]="chartOptions()" [style]="{'width': '100%', 'height': '100%'}" />
        <!-- Center text — when the legend is shown at the bottom, Chart.js
             shifts the donut up to make room. We mirror that shift here
             with a bottom margin so the text stays centered IN the donut,
             not in the whole canvas. -->
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none"
             [class.pb-6]="showLegend()">
          <div class="text-center">
            <span [class]="showLegend() ? 'text-2xl font-bold text-fg' : 'text-xl font-bold text-fg'">
              {{ winRate() }}%
            </span>
            <span class="block text-[10px] text-fg-muted uppercase tracking-wider">Win Rate</span>
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
  /** When false, hides the bottom legend — the donut then fills the canvas
   *  symmetrically and the center text sits exactly in its hole. Use for
   *  compact panels where the legend wastes space. */
  showLegend = input<boolean>(true);

  private theme = useChartTheme();

  winRate = computed(() => {
    const total = this.wins() + this.losses();
    if (total === 0) return 0;
    return Math.round((this.wins() / total) * 100);
  });

  chartOptions = computed<ChartOptions<'doughnut'>>(() => {
    const t = this.theme();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      cutout: '65%',
      plugins: {
        legend: {
          display: this.showLegend(),
          position: 'bottom',
          labels: {
            color: t.tickColor,
            padding: 16,
            usePointStyle: true,
            pointStyleWidth: 10,
          },
        },
        tooltip: {
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          borderWidth: 1,
          titleColor: t.tooltipTitle,
          bodyColor: t.tooltipBody,
          padding: 10,
          cornerRadius: 8,
        },
      },
    };
  });

  chartData = computed<ChartData<'doughnut'>>(() => {
    const t = this.theme();
    const data = [];
    const labels = [];
    const colors = [];

    if (this.wins() > 0) {
      data.push(this.wins());
      labels.push('Wins');
      colors.push(t.positive);
    }
    if (this.losses() > 0) {
      data.push(this.losses());
      labels.push('Losses');
      colors.push(t.negative);
    }
    if (this.breakeven() > 0) {
      data.push(this.breakeven());
      labels.push('Breakeven');
      colors.push(t.info);
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
