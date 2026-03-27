import { Component, computed, input } from '@angular/core';
import { BaseChartDirective } from 'ng2-charts';
import { ChartData, ChartOptions } from 'chart.js';
import { DARK_THEME, CHART_COLORS } from './chart-defaults';
import { TradeListItem } from '../../../../models/trade.model';

@Component({
  selector: 'app-trade-pnl-chart',
  standalone: true,
  imports: [BaseChartDirective],
  template: `
    <div class="h-full w-full min-h-[200px]">
      @if (trades().length > 0) {
        <canvas baseChart
          type="bar"
          [data]="chartData()"
          [options]="chartOptions">
        </canvas>
      } @else {
        <div class="flex items-center justify-center h-full text-fg-faint text-sm">No trade data available</div>
      }
    </div>
  `,
})
export class TradePnlChartComponent {
  trades = input.required<TradeListItem[]>();

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
        ticks: { color: DARK_THEME.tickColor, maxRotation: 45, maxTicksLimit: 20 },
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
    const trades = this.trades();
    const pnls = trades.map(t => t.total_realized_pnl ?? 0);
    return {
      labels: trades.map(t => t.display_symbol || `Trade #${t.id}`),
      datasets: [{
        data: pnls,
        backgroundColor: pnls.map(v => v >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative),
        borderRadius: 4,
        maxBarThickness: 40,
      }],
    };
  });
}
