import { Component, computed, input } from '@angular/core';
import { UIChart } from 'primeng/chart';
import { ChartData, ChartOptions } from 'chart.js';
import { useChartTheme } from './chart-defaults';
import { TradeListItem } from '../../../../models/trade.model';

@Component({
  selector: 'app-trade-pnl-chart',
  standalone: true,
  imports: [UIChart],
  styles: [`:host { display: block; height: 100%; }`],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (trades().length > 0) {
        <p-chart type="bar" [data]="chartData()" [options]="chartOptions()" [style]="{'width': '100%', 'height': '100%'}" />
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class TradePnlChartComponent {
  trades = input.required<TradeListItem[]>();

  private theme = useChartTheme();

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
            label: (item) => {
              const val = item.raw as number;
              return `P&L: $${val.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: t.tickColor, maxRotation: 45, maxTicksLimit: 20 },
          grid: { color: t.gridColor },
        },
        y: {
          ticks: {
            color: t.tickColor,
            callback: (value) => `$${value}`,
          },
          grid: { color: t.gridColor },
        },
      },
    };
  });

  chartData = computed<ChartData<'bar'>>(() => {
    const t = this.theme();
    const trades = this.trades();
    const pnls = trades.map((td) => td.total_realized_pnl ?? 0);
    return {
      labels: trades.map((td) => td.display_symbol || `Trade #${td.id}`),
      datasets: [{
        data: pnls,
        backgroundColor: pnls.map((v) => (v >= 0 ? t.positive : t.negative)),
        borderRadius: 4,
        maxBarThickness: 40,
      }],
    };
  });
}
