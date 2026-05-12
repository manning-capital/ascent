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
import { UIChart } from 'primeng/chart';
import { Skeleton } from 'primeng/skeleton';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import { Plugin } from 'chart.js';
import { Subscription } from 'rxjs';
import { timeout } from 'rxjs/operators';

import { ContextService } from '../../../services/context.service';
import { ChartData, ChartOptions } from 'chart.js';

import { ContextResponse, Plot } from '../../../models/context.model';
import { TradeStatus } from '../../../models/trade.model';
import {
  TRADE_MARKERS_PLUGIN_ID,
  TradeMarkersOptions,
  buildChartDataForPlot,
  buildChartOptionsForPlot,
  buildChartTheme,
  toEpochMs,
} from './run-context-chart.config';

const ACTIVE_TAB_KEY_PREFIX = 'ascent.run-context.active-tab';

const tradeMarkersPlugin: Plugin<'line'> = {
  id: TRADE_MARKERS_PLUGIN_ID,
  // Shade the off-trade regions BEFORE the datasets render so the line
  // and points stay fully visible on top of the wash.
  beforeDatasetsDraw(chart, _args, opts) {
    const options = opts as unknown as TradeMarkersOptions | undefined;
    if (!options || !options.outOfRangeFill) return;
    const xScale = chart.scales['x'];
    const yScale = chart.scales['y'];
    if (!xScale || !yScale) return;
    const ctx = chart.ctx;
    const left = xScale.left;
    const right = xScale.right;
    const top = yScale.top;
    const bottom = yScale.bottom;

    const fillRect = (xStart: number, xEnd: number): void => {
      if (xEnd <= xStart) return;
      ctx.save();
      ctx.fillStyle = options.outOfRangeFill;
      ctx.fillRect(xStart, top, xEnd - xStart, bottom - top);
      ctx.restore();
    };

    if (options.entryMs !== null) {
      const entryPx = xScale.getPixelForValue(options.entryMs);
      if (Number.isFinite(entryPx)) {
        fillRect(left, Math.min(Math.max(entryPx, left), right));
      }
    }
    if (options.exitMs !== null) {
      const exitPx = xScale.getPixelForValue(options.exitMs);
      if (Number.isFinite(exitPx)) {
        fillRect(Math.min(Math.max(exitPx, left), right), right);
      }
    }
  },
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
      ctx.fillStyle = options.labelColor || color;
      ctx.font = '11px sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText(label, x + 4, yScale.top + 4);
      ctx.restore();
    };

    if (options.entryMs !== null) drawLine(options.entryMs, options.entryColor, 'Entry');
    if (options.exitMs !== null) drawLine(options.exitMs, options.exitColor, 'Exit');
  },
};

@Component({
  selector: 'app-run-context-chart',
  standalone: true,
  imports: [UIChart, Skeleton, Tabs, TabList, Tab, TabPanels, TabPanel],
  // Renders the chart content only — no surrounding card. The caller is
  // expected to provide the visual frame (heading, border, padding, AND a
  // fixed height) and we fill that box in every state so the page doesn't
  // jump when the data finishes loading or errors out.
  template: `
    @if (!strategyRunId()) {
      <div class="h-full flex items-center justify-center text-sm text-fg-muted px-4">
        Context not available for this trade.
      </div>
    } @else if (loading()) {
      <div class="h-full p-4">
        <p-skeleton width="100%" height="100%"/>
      </div>
    } @else if (errorMessage()) {
      <div class="h-full flex items-center justify-center text-sm text-negative px-4">
        {{ errorMessage() }}
      </div>
    } @else if (!response() || response()!.series.length === 0) {
      <div class="h-full flex items-center justify-center text-sm text-fg-muted px-4">
        No context data available for this run yet.
      </div>
    } @else if (plots().length === 0) {
      <div class="h-full flex items-center justify-center text-sm text-fg-muted px-4">
        No plots configured for this strategy.
      </div>
    } @else if (plots().length === 1) {
      <div class="h-full flex flex-col px-4 pt-2 pb-4">
        <div class="text-xs font-medium text-fg-muted mb-2 shrink-0">{{ plots()[0].title }}</div>
        <div class="flex-1 min-h-0 w-full">
          <p-chart
            type="line"
            [data]="chartData()[plots()[0].id]"
            [options]="chartOptions()[plots()[0].id]"
            [plugins]="chartPlugins"
            [style]="{ width: '100%', height: '100%' }"/>
        </div>
      </div>
    } @else {
      <p-tabs class="h-full flex flex-col" [value]="activeTabId() ?? plots()[0].id" (valueChange)="onTabChange($event)">
        <p-tablist>
          @for (plot of plots(); track plot.id) {
            <p-tab [value]="plot.id">{{ plot.title }}</p-tab>
          }
        </p-tablist>
        <p-tabpanels class="flex-1 min-h-0">
          @for (plot of plots(); track plot.id) {
            <p-tabpanel [value]="plot.id" class="h-full">
              <div class="h-full w-full px-4 pb-4">
                <p-chart
                  type="line"
                  [data]="chartData()[plot.id]"
                  [options]="chartOptions()[plot.id]"
                  [plugins]="chartPlugins"
                  [style]="{ width: '100%', height: '100%' }"/>
              </div>
            </p-tabpanel>
          }
        </p-tabpanels>
      </p-tabs>
    }
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
  currentStatus = input<string | null>(null);
  statuses = input<TradeStatus[]>([]);

  // Trades in terminal states have no further ticks to stream — render
  // them statically with the historical time scale even when ``exit_at``
  // happens to be null (e.g. CANCELLED before any open).
  private readonly TERMINAL_STATUSES = new Set([
    'CLOSED',
    'CANCELLED',
    'REJECTED',
    'ERROR',
  ]);

  private isTradeLive(): boolean {
    const status = this.currentStatus();
    if (status && this.TERMINAL_STATUSES.has(status)) return false;
    return !this.end();
  }

  loading = signal(true);
  errorMessage = signal<string | null>(null);
  response = signal<ContextResponse | null>(null);
  activeTabId = signal<string | null>(null);

  private streamSub: Subscription | null = null;
  private receivedFirstEvent = false;

  readonly chartPlugins = [tradeMarkersPlugin];

  plots = computed<Plot[]>(() => this.response()?.trade_view?.plots ?? []);

  // Options change rarely — only when the structural plot config or the
  // trade's open/closed state changes. Cached by a stable key so PrimeNG's
  // <p-chart> doesn't see an identity change and reinit the Chart.js
  // instance on every SSE tick (the main jitter source).
  private optionsCache = new Map<string, ChartOptions<'line'>>();

  chartOptions = computed<Record<string, ChartOptions<'line'>>>(() => {
    const plots = this.plots();
    const tradeView = this.response()?.trade_view;
    const showMarkers = tradeView?.show_trade_markers !== false;
    const entryMs = toEpochMs(this.start());
    const exitMs = toEpochMs(this.end());
    const isOpen = this.isTradeLive();
    const theme = buildChartTheme();
    const out: Record<string, ChartOptions<'line'>> = {};
    for (const plot of plots) {
      const key = JSON.stringify({
        plot,
        showMarkers,
        entryMs,
        exitMs,
        isOpen,
      });
      let cached = this.optionsCache.get(key);
      if (!cached) {
        cached = buildChartOptionsForPlot({
          plot,
          showTradeMarkers: showMarkers,
          entryMs,
          exitMs,
          isOpen,
          theme,
        });
        this.optionsCache.set(key, cached);
      }
      out[plot.id] = cached;
    }
    return out;
  });

  chartData = computed<Record<string, ChartData<'line'>>>(() => {
    const r = this.response();
    if (!r) return {};
    const tradeView = r.trade_view;
    const showOverlay = tradeView?.show_trade_status_overlay !== false;
    const out: Record<string, ChartData<'line'>> = {};
    for (const plot of this.plots()) {
      out[plot.id] = buildChartDataForPlot({
        plot,
        contextSeries: r.series,
        statuses: this.statuses(),
        showStatusOverlay: showOverlay,
      });
    }
    return out;
  });

  constructor() {
    effect(() => {
      const r = this.response();
      const runId = this.strategyRunId();
      if (!r || !runId) return;
      const plots = this.plots();
      if (plots.length === 0) {
        this.activeTabId.set(null);
        return;
      }
      const stored = loadActiveTab(runId);
      const validIds = new Set(plots.map(p => p.id));
      const current = this.activeTabId();
      if (current && validIds.has(current)) return;
      if (stored && validIds.has(stored)) {
        this.activeTabId.set(stored);
        return;
      }
      this.activeTabId.set(plots[0].id);
    });

    effect((onCleanup) => {
      const sid = this.strategyId();
      const rid = this.strategyRunId();
      if (!rid) return;
      const isOpen = this.isTradeLive();
      this.receivedFirstEvent = false;
      if (isOpen) {
        const sub = this.contextService
          .streamStrategyRunContext(sid, rid, {
            start: this.start(),
            end: this.end(),
            tradeId: this.tradeId(),
          })
          .subscribe({
            next: response => {
              this.response.set(response);
              if (!this.receivedFirstEvent) {
                this.receivedFirstEvent = true;
                this.loading.set(false);
                this.errorMessage.set(null);
              }
            },
            error: err => {
              console.error('Context SSE subscription failed', err);
              if (!this.receivedFirstEvent) {
                this.errorMessage.set('Failed to load strategy context. See console.');
                this.loading.set(false);
              }
            },
          });
        this.streamSub = sub;
        onCleanup(() => sub.unsubscribe());
      } else {
        const sub = this.contextService
          .loadStrategyRunContext(sid, rid, {
            start: this.start(),
            end: this.end(),
            tradeId: this.tradeId(),
          })
          .pipe(timeout(20_000))
          .subscribe({
            next: response => {
              this.response.set(response);
              this.loading.set(false);
              this.errorMessage.set(null);
            },
            error: err => {
              console.error('Failed to load run context', err);
              const status = typeof err?.status === 'number' ? ` (status ${err.status})` : '';
              this.errorMessage.set(
                `Failed to load strategy context${status}. See console.`,
              );
              this.loading.set(false);
            },
          });
        this.streamSub = sub;
        onCleanup(() => sub.unsubscribe());
      }
    });
  }

  ngOnInit(): void {
    if (!this.strategyRunId()) {
      this.loading.set(false);
    }
  }

  ngOnDestroy(): void {
    this.streamSub?.unsubscribe();
    this.streamSub = null;
  }

  onTabChange(value: string | number | undefined): void {
    if (value === undefined) return;
    const id = String(value);
    this.activeTabId.set(id);
    const runId = this.strategyRunId();
    if (runId) saveActiveTab(runId, id);
  }
}

function loadActiveTab(runId: string): string | null {
  try {
    return localStorage.getItem(`${ACTIVE_TAB_KEY_PREFIX}:${runId}`);
  } catch {
    return null;
  }
}

function saveActiveTab(runId: string, tabId: string): void {
  try {
    localStorage.setItem(`${ACTIVE_TAB_KEY_PREFIX}:${runId}`, tabId);
  } catch {
    // localStorage can be unavailable (private mode, quota) — silent.
  }
}
