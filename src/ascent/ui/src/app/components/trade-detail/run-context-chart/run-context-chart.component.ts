import {
  Component,
  OnDestroy,
  OnInit,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MultiSelect } from 'primeng/multiselect';
import { Card } from 'primeng/card';
import { UIChart } from 'primeng/chart';
import { Skeleton } from 'primeng/skeleton';
import { ChartData, ChartOptions, Plugin } from 'chart.js';
import { Subscription, interval } from 'rxjs';
import { timeout } from 'rxjs/operators';
import { ContextService } from '../../../services/context.service';
import { ContextResponse, ContextSeries, TradeView } from '../../../models/context.model';
import { DARK_THEME } from '../../strategies/strategy-detail/charts/chart-defaults';

interface SeriesOption {
  label: string;
  value: string;
}

const PALETTE = [
  '#22c55e',
  '#ef4444',
  '#3b82f6',
  '#eab308',
  '#a855f7',
  '#14b8a6',
  '#f97316',
  '#ec4899',
];

const STORAGE_KEY_PREFIX = 'ascent.run-context.defaults';
const INTERESTING_KEYWORDS = [
  'spread',
  'entry',
  'exit',
  'level',
  'mu',
  'theta',
  'z_score',
  'zscore',
];

const TRADE_MARKERS_PLUGIN_ID = 'tradeMarkers';

// Open trades have no exit_at, so the initial load is a snapshot. Poll the
// context endpoint while the trade is open so the spread/theta/entry/exit
// series advance in (near) real time. Cadence aligns with strategy ticks
// (when evaluation actually runs and decisions are made), not feed publish
// cadence — the strategy's view is the meaningful unit of "new data".
const LIVE_POLL_INTERVAL_MS = 1000;

interface TradeMarkersOptions {
  entryMs: number | null;
  exitMs: number | null;
}

// Inline plugin: draws vertical reference lines at the trade's entry_at and
// exit_at on the x-scale. Uses Chart.js core only — no annotation plugin
// dependency. Plugin options are read per-chart from `options.plugins.tradeMarkers`.
const tradeMarkersPlugin: Plugin<'line'> = {
  id: TRADE_MARKERS_PLUGIN_ID,
  afterDatasetsDraw(chart, _args, opts) {
    const options = opts as unknown as TradeMarkersOptions | undefined;
    if (!options) return;
    const xScale = chart.scales['x'];
    const yScale = chart.scales['y'];
    if (!xScale || !yScale) return;
    const ctx = chart.ctx;

    const drawLine = (xValue: number, color: string, label: string): void => {
      if (xValue < xScale.min || xValue > xScale.max) return;
      const x = xScale.getPixelForValue(xValue);
      if (!Number.isFinite(x)) return;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x, yScale.top);
      ctx.lineTo(x, yScale.bottom);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = color;
      ctx.setLineDash([4, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = color;
      ctx.font = '11px sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText(label, x + 4, yScale.top + 4);
      ctx.restore();
    };

    if (options.entryMs !== null) drawLine(options.entryMs, '#22c55e', 'Entry');
    if (options.exitMs !== null) drawLine(options.exitMs, '#ef4444', 'Exit');
  },
};

@Component({
  selector: 'app-run-context-chart',
  standalone: true,
  imports: [FormsModule, MultiSelect, Card, UIChart, Skeleton],
  template: `
    <p-card header="Strategy Context">
      @if (!strategyRunId()) {
        <div class="text-sm text-surface-500 py-4">
          Context not available for this trade.
        </div>
      } @else if (loading()) {
        <p-skeleton width="100%" height="18rem"/>
      } @else if (errorMessage()) {
        <div class="text-sm text-red-500 py-4">
          {{ errorMessage() }}
        </div>
      } @else if (!response() || response()!.series.length === 0) {
        <div class="text-sm text-surface-500 py-4">
          No context data available for this run yet.
        </div>
      } @else {
        <div class="flex flex-col gap-3">
          <p-multiSelect
            [options]="seriesOptions()"
            [(ngModel)]="selectedSeries"
            optionLabel="label"
            optionValue="value"
            placeholder="Select series to plot"
            display="chip"
            [filter]="true"
            [showClear]="false"
            styleClass="w-full"/>
          <div class="h-80 w-full">
            @if (selectedSeries().length === 0) {
              <div class="flex items-center justify-center h-full text-sm text-surface-500">
                Pick one or more series above to plot.
              </div>
            } @else {
              <p-chart
                type="line"
                [data]="chartData()"
                [options]="chartOptions()"
                [plugins]="chartPlugins"
                [style]="{ width: '100%', height: '100%' }"/>
            }
          </div>
        </div>
      }
    </p-card>
  `,
  styles: [`:host { display: block; }`],
})
export class RunContextChartComponent implements OnInit, OnDestroy {
  private contextService = inject(ContextService);

  strategyId = input.required<string>();
  strategyRunId = input.required<string | null>();
  tradeId = input<string | null>(null);
  start = input<string | null>(null);
  end = input<string | null>(null);

  loading = signal(true);
  errorMessage = signal<string | null>(null);
  response = signal<ContextResponse | null>(null);
  selectedSeries = signal<string[]>([]);

  private fetchSub: Subscription | null = null;

  // Plugin instances are passed per-chart so we don't need a global Chart.register().
  readonly chartPlugins = [tradeMarkersPlugin];

  private seriesLabel(series: ContextSeries, tradeView: TradeView | null): string {
    const override = tradeView?.series_labels?.[series.attribute.name];
    return override ?? series.display_name;
  }

  seriesOptions = computed<SeriesOption[]>(() => {
    const r = this.response();
    if (!r) return [];
    return r.series.map(s => ({ label: this.seriesLabel(s, r.trade_view), value: s.name }));
  });

  // Per-tick options so the trade-marker plugin and tick formatter can react
  // to inputs (entry/exit timestamps) and the loaded response.
  chartOptions = computed<ChartOptions<'line'>>(() => {
    const tradeView = this.response()?.trade_view ?? null;
    const showMarkers = tradeView?.show_trade_markers !== false;
    const entryMs = showMarkers ? toEpochMs(this.start()) : null;
    const exitMs = showMarkers ? toEpochMs(this.end()) : null;

    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { labels: { color: DARK_THEME.tickColor } },
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
              const v = items[0]?.parsed?.x;
              return typeof v === 'number' ? formatEpochFull(v) : '';
            },
          },
        },
        // Read by tradeMarkersPlugin via opts argument.
        [TRADE_MARKERS_PLUGIN_ID]: { entryMs, exitMs } as TradeMarkersOptions,
      },
      scales: {
        x: {
          type: 'linear',
          ticks: {
            color: DARK_THEME.tickColor,
            maxTicksLimit: 10,
            callback: (value) =>
              typeof value === 'number' ? formatEpochTime(value) : String(value),
          },
          grid: { color: DARK_THEME.gridColor },
        },
        y: {
          ticks: { color: DARK_THEME.tickColor },
          grid: { color: DARK_THEME.gridColor },
        },
      },
    };
  });

  // Each series carries its own native timestamps. Points are emitted as
  // {x: epochMs, y: value} tuples on a linear x-axis so the trade-markers
  // plugin can position vertical lines at exact entry/exit timestamps
  // without needing a time-scale adapter.
  chartData = computed<ChartData<'line'>>(() => {
    const r = this.response();
    const selected = new Set(this.selectedSeries());
    if (!r || selected.size === 0) return { datasets: [] };

    const wanted = r.series.filter(s => selected.has(s.name));
    const datasets = wanted.map((series, idx) => {
      const color = PALETTE[idx % PALETTE.length];
      const data = series.points
        .map(p => ({ x: Date.parse(p.t), y: p.v }))
        .filter(point => Number.isFinite(point.x));
      return {
        label: this.seriesLabel(series, r.trade_view),
        data,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0,
        stepped: true as const,
        spanGaps: true,
      };
    });

    return { datasets };
  });

  constructor() {
    effect(() => {
      const r = this.response();
      const runId = this.strategyRunId();
      if (!r || !runId) return;
      if (this.selectedSeries().length > 0) return;
      const stored = loadStoredDefaults(runId);
      const available = new Set(r.series.map(s => s.name));
      const storedValid = stored.filter(name => available.has(name));
      if (storedValid.length > 0) {
        this.selectedSeries.set(storedValid);
        return;
      }
      const fromTradeView = pickFromTradeView(r.series, r.trade_view);
      if (fromTradeView.length > 0) {
        this.selectedSeries.set(fromTradeView);
        return;
      }
      this.selectedSeries.set(pickDefaultSeries(r.series));
    });

    effect(() => {
      const runId = this.strategyRunId();
      const selection = this.selectedSeries();
      if (!runId) return;
      saveStoredDefaults(runId, selection);
    });

    // Live polling while the trade is open (no exit_at). The effect tears
    // down the interval automatically when end() becomes set or the run id
    // changes, so a trade that closes while the page is open stops polling.
    effect((onCleanup) => {
      const runId = this.strategyRunId();
      const isOpen = !this.end();
      if (!runId || !isOpen) return;
      const sub = interval(LIVE_POLL_INTERVAL_MS).subscribe(() => {
        this.fetchContext({ silent: true });
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  ngOnInit(): void {
    if (!this.strategyRunId()) {
      this.loading.set(false);
      return;
    }
    this.fetchContext({ silent: false });
  }

  ngOnDestroy(): void {
    this.fetchSub?.unsubscribe();
    this.fetchSub = null;
  }

  private fetchContext({ silent }: { silent: boolean }): void {
    const sid = this.strategyId();
    const rid = this.strategyRunId();
    if (!rid) return;
    this.fetchSub?.unsubscribe();
    this.fetchSub = this.contextService
      .loadStrategyRunContext(sid, rid, {
        start: this.start(),
        end: this.end(),
        tradeId: this.tradeId(),
      })
      .pipe(timeout(20_000))
      .subscribe({
        next: response => {
          this.response.set(response);
          if (!silent) {
            this.loading.set(false);
            this.errorMessage.set(null);
          }
        },
        error: err => {
          console.error('Failed to load run context', err);
          if (silent) return;
          const status = typeof err?.status === 'number' ? ` (status ${err.status})` : '';
          this.errorMessage.set(`Failed to load strategy context${status}. See console.`);
          this.loading.set(false);
        },
      });
  }
}

function toEpochMs(iso: string | null): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

function formatEpochTime(ms: number): string {
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return String(ms);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatEpochFull(ms: number): string {
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return String(ms);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function pickFromTradeView(series: ContextSeries[], tradeView: TradeView | null): string[] {
  if (!tradeView || tradeView.series.length === 0) return [];
  const picks: string[] = [];
  for (const wanted of tradeView.series) {
    for (const s of series) {
      if (s.attribute.name === wanted) picks.push(s.name);
    }
  }
  return picks;
}

function pickDefaultSeries(series: ContextSeries[]): string[] {
  const interesting = series.filter(s => {
    const lower = s.attribute.name.toLowerCase();
    return INTERESTING_KEYWORDS.some(k => lower.includes(k));
  });
  if (interesting.length > 0) return interesting.map(s => s.name);
  return series.slice(0, 4).map(s => s.name);
}

function loadStoredDefaults(runId: string): string[] {
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}:${runId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function saveStoredDefaults(runId: string, series: string[]): void {
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}:${runId}`, JSON.stringify(series));
  } catch {
    // localStorage can be unavailable (private mode, quota) — silent.
  }
}
