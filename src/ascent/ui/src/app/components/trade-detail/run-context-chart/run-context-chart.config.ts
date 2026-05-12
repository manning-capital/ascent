import { Chart, ChartData, ChartOptions, ScriptableContext } from 'chart.js';
import 'chartjs-adapter-luxon';
import streamingRegisterables from '@robloche/chartjs-plugin-streaming';
import zoomPlugin from 'chartjs-plugin-zoom';

import {
  ColorToken,
  ContextSeries,
  LineStyle,
  Plot,
  PlotSeries,
  SeriesPoint,
  SeriesStyle,
} from '../../../models/context.model';

// Register the streaming scale + plugin and the zoom plugin globally. Idempotent.
let pluginsRegistered = false;
function ensurePluginsRegistered(): void {
  if (pluginsRegistered) return;
  Chart.register(...streamingRegisterables, zoomPlugin);
  pluginsRegistered = true;
}

const LIVE_WINDOW_MS = 5 * 60 * 1000;
const LIVE_REFRESH_MS = 1000;
const LIVE_DELAY_MS = 2000;
const LIVE_FRAME_RATE = 30;
const CLOSED_TRADE_PADDING_MS = 30 * 1000;

export interface TradeStatusEvent {
  timestamp: string;
  status: string;
}

const TRADE_MARKERS_PLUGIN_ID = 'tradeMarkers';

export interface TradeMarkersOptions {
  entryMs: number | null;
  exitMs: number | null;
  entryColor: string;
  exitColor: string;
  labelColor: string;
  outOfRangeFill: string;
}

export interface BuiltChart {
  data: ChartData<'line'>;
  options: ChartOptions<'line'>;
}

export interface BuildChartOptionsContext {
  plot: Plot;
  showTradeMarkers: boolean;
  entryMs: number | null;
  exitMs: number | null;
  isOpen: boolean;
  theme: ChartTheme;
}

export interface BuildChartDataContext {
  plot: Plot;
  contextSeries: ContextSeries[];
  statuses: TradeStatusEvent[];
  showStatusOverlay: boolean;
}

const AUTO_PALETTE: ColorToken[] = [
  'primary',
  'success',
  'info',
  'warning',
  'danger',
  'secondary',
];

const TOKEN_VAR_FALLBACKS: Record<ColorToken, string[]> = {
  primary: ['--p-primary-color', '--color-info'],
  secondary: ['--p-text-muted-color', '--color-graph-accent-1', '--fg-muted'],
  success: ['--p-green-500', '--p-success-color', '--color-positive'],
  info: ['--p-blue-500', '--p-info-color', '--color-info'],
  warning: ['--p-amber-500', '--p-warning-color', '--color-warning'],
  danger: ['--p-red-500', '--p-danger-color', '--color-negative'],
  neutral: ['--p-text-color', '--fg'],
  muted: ['--p-text-muted-color', '--fg-muted'],
};

export const STATUS_OVERLAY_DEFAULTS: Record<string, SeriesStyle> = {
  PENDING: defaultStatusStyle('muted', 'cross', 4),
  OPENING: defaultStatusStyle('warning', 'circle', 5),
  OPEN: defaultStatusStyle('success', 'circle', 6),
  CLOSING: defaultStatusStyle('warning', 'cross', 5),
  CLOSED: defaultStatusStyle('neutral', 'circle', 5),
  CANCELLED: defaultStatusStyle('muted', 'rectRot', 5),
  REJECTED: defaultStatusStyle('danger', 'cross', 5),
  ERROR: defaultStatusStyle('danger', 'triangle', 6),
};

function defaultStatusStyle(
  color: ColorToken,
  point_style: SeriesStyle['point_style'],
  point_radius: number,
): SeriesStyle {
  return {
    color,
    line_style: 'solid',
    line_width: 0,
    opacity: 1,
    point_radius,
    point_style,
    fill: false,
  };
}

export function lineDashFor(style: LineStyle): number[] {
  switch (style) {
    case 'dashed':
      return [6, 4];
    case 'dotted':
      return [2, 3];
    default:
      return [];
  }
}

export function readCssVar(name: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return '';
  }
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function firstResolvedVar(varNames: string[]): string {
  for (const name of varNames) {
    const value = readCssVar(name);
    if (value) return value;
  }
  return '';
}

function applyOpacity(color: string, opacity: number): string {
  if (!color) return `rgba(148, 163, 184, ${clampOpacity(opacity)})`;
  const trimmed = color.trim();
  const rgb = parseRgbTriplet(trimmed);
  if (rgb) {
    return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${clampOpacity(opacity)})`;
  }
  // Fallback: pass through; Chart.js will accept any CSS color but opacity won't apply.
  return trimmed;
}

function clampOpacity(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.max(0, Math.min(1, value));
}

function parseRgbTriplet(value: string): [number, number, number] | null {
  if (value.startsWith('#')) {
    const hex = value.slice(1);
    if (hex.length === 3) {
      const [r, g, b] = hex.split('').map(c => parseInt(c + c, 16));
      return [r, g, b];
    }
    if (hex.length === 6) {
      return [
        parseInt(hex.slice(0, 2), 16),
        parseInt(hex.slice(2, 4), 16),
        parseInt(hex.slice(4, 6), 16),
      ];
    }
    return null;
  }
  const match = /rgba?\(\s*([0-9.]+)[ ,]+([0-9.]+)[ ,]+([0-9.]+)/i.exec(value);
  if (match) {
    return [Number(match[1]), Number(match[2]), Number(match[3])];
  }
  return null;
}

function hashSeriesName(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function autoToken(seriesName: string): ColorToken {
  return AUTO_PALETTE[hashSeriesName(seriesName) % AUTO_PALETTE.length];
}

export function resolveColor(
  token: ColorToken | null,
  seriesName: string,
  opacity: number,
): string {
  const finalToken: ColorToken = token ?? autoToken(seriesName);
  const raw = firstResolvedVar(TOKEN_VAR_FALLBACKS[finalToken]);
  return applyOpacity(raw, opacity);
}

export function sampleSeriesAt(points: SeriesPoint[], iso: string): number | null {
  const target = Date.parse(iso);
  if (!Number.isFinite(target)) return null;
  let chosen: number | null = null;
  for (const p of points) {
    const t = Date.parse(p.t);
    if (!Number.isFinite(t) || t > target) break;
    chosen = p.v;
  }
  return chosen;
}

export interface ChartTheme {
  tickColor: string;
  gridColor: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipTitle: string;
  tooltipBody: string;
  entryMarkerColor: string;
  exitMarkerColor: string;
  axisLabelColor: string;
  outOfRangeFill: string;
}

export function buildChartTheme(): ChartTheme {
  const muted = firstResolvedVar(TOKEN_VAR_FALLBACKS.muted);
  const neutral = firstResolvedVar(TOKEN_VAR_FALLBACKS.neutral);
  const border = firstResolvedVar([
    '--p-content-border-color',
    '--edge',
    '--edge-dim',
  ]);
  const surface = firstResolvedVar([
    '--p-overlay-modal-background',
    '--p-content-background',
    '--surface',
    '--elevated',
  ]);
  return {
    tickColor: muted,
    axisLabelColor: muted,
    gridColor: border || 'rgba(148, 163, 184, 0.15)',
    tooltipBg: surface,
    tooltipBorder: border || 'rgba(148, 163, 184, 0.25)',
    tooltipTitle: neutral,
    tooltipBody: muted,
    entryMarkerColor: applyOpacity(
      firstResolvedVar(TOKEN_VAR_FALLBACKS.success),
      1,
    ),
    exitMarkerColor: applyOpacity(
      firstResolvedVar(TOKEN_VAR_FALLBACKS.danger),
      1,
    ),
    outOfRangeFill: applyOpacity(
      firstResolvedVar(TOKEN_VAR_FALLBACKS.muted),
      0.12,
    ),
  };
}


export function buildChartOptionsForPlot(
  ctx: BuildChartOptionsContext,
): ChartOptions<'line'> {
  ensurePluginsRegistered();
  return buildChartOptions(ctx);
}

export function buildChartDataForPlot(ctx: BuildChartDataContext): ChartData<'line'> {
  const datasets: ChartData<'line'>['datasets'] = [];

  for (const plotSeries of ctx.plot.series) {
    const matches = ctx.contextSeries.filter(
      s => s.attribute.name === plotSeries.name,
    );
    for (const match of matches) {
      datasets.push(buildLineDataset(plotSeries, match));
    }
  }

  if (ctx.showStatusOverlay && ctx.plot.main_series_name) {
    const main = ctx.contextSeries.find(
      s => s.attribute.name === ctx.plot.main_series_name,
    );
    if (main) {
      const overlay = buildStatusOverlay(main, ctx.statuses);
      if (overlay) datasets.push(overlay);
    }
  }

  return { datasets };
}

function buildLineDataset(
  plotSeries: PlotSeries,
  ctxSeries: ContextSeries,
): ChartData<'line'>['datasets'][number] {
  const style = plotSeries.style;
  const color = resolveColor(style.color, ctxSeries.name, style.opacity);
  const data = ctxSeries.points
    .map(p => ({ x: Date.parse(p.t), y: p.v }))
    .filter(p => Number.isFinite(p.x))
    .sort((a, b) => a.x - b.x);
  return {
    label: plotSeries.label ?? ctxSeries.display_name,
    data,
    borderColor: color,
    backgroundColor: color,
    borderWidth: style.line_width,
    borderDash: lineDashFor(style.line_style),
    pointRadius: style.point_radius,
    pointHoverRadius: Math.max(style.point_radius, 4),
    pointStyle: style.point_style,
    tension: 0,
    spanGaps: false,
    fill: style.fill,
  };
}

function buildStatusOverlay(
  main: ContextSeries,
  statuses: TradeStatusEvent[],
): ChartData<'line'>['datasets'][number] | null {
  const points = statuses
    .map(event => {
      const x = Date.parse(event.timestamp);
      if (!Number.isFinite(x)) return null;
      const y = sampleSeriesAt(main.points, event.timestamp);
      if (y === null) return null;
      return { x, y, status: event.status };
    })
    .filter((p): p is { x: number; y: number; status: string } => p !== null);
  if (points.length === 0) return null;

  return {
    label: 'Trade Lifecycle',
    data: points.map(p => ({ x: p.x, y: p.y })),
    showLine: false,
    borderWidth: 0,
    pointRadius: (ctx: ScriptableContext<'line'>) =>
      styleFor(points[ctx.dataIndex]?.status).point_radius,
    pointHoverRadius: (ctx: ScriptableContext<'line'>) =>
      styleFor(points[ctx.dataIndex]?.status).point_radius + 2,
    pointStyle: (ctx: ScriptableContext<'line'>) =>
      styleFor(points[ctx.dataIndex]?.status).point_style,
    pointBackgroundColor: (ctx: ScriptableContext<'line'>) =>
      colorForStatus(points[ctx.dataIndex]?.status),
    pointBorderColor: (ctx: ScriptableContext<'line'>) =>
      colorForStatus(points[ctx.dataIndex]?.status),
    animation: false,
  } as ChartData<'line'>['datasets'][number];
}

function styleFor(status: string | undefined): SeriesStyle {
  if (status && STATUS_OVERLAY_DEFAULTS[status]) {
    return STATUS_OVERLAY_DEFAULTS[status];
  }
  return defaultStatusStyle('muted', 'circle', 4);
}

function colorForStatus(status: string | undefined): string {
  const style = styleFor(status);
  return resolveColor(style.color, `status:${status ?? 'unknown'}`, style.opacity);
}

function buildChartOptions(ctx: BuildChartOptionsContext): ChartOptions<'line'> {
  const { theme, plot, showTradeMarkers, entryMs, exitMs, isOpen } = ctx;
  const xScale = isOpen
    ? buildRealtimeScale(theme)
    : buildHistoricalScale(theme, entryMs, exitMs);
  const zoomLimits = isOpen ? undefined : buildZoomLimits(entryMs, exitMs);
  return {
    responsive: true,
    maintainAspectRatio: false,
    // Animations are off at the data layer — the streaming plugin's own
    // refresh loop drives the smooth horizontal scroll for live data, and
    // closed-trade renders are static. Y-axis stays put (no bounce).
    animation: false,
    animations: {
      colors: false,
      numbers: false,
    },
    transitions: {
      active: { animation: { duration: 0 } },
      resize: { animation: { duration: 0 } },
      show: { animation: { duration: 0 } },
      hide: { animation: { duration: 0 } },
    },
    interaction: {
      intersect: false,
      mode: 'nearest',
      axis: 'x',
    },
    plugins: {
      legend: {
        display: plot.show_legend,
        position: plot.legend_position,
        labels: { color: theme.axisLabelColor },
      },
      tooltip: {
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        borderWidth: 1,
        titleColor: theme.tooltipTitle,
        bodyColor: theme.tooltipBody,
        padding: 10,
        cornerRadius: 8,
        callbacks: {
          title: (items) => {
            const v = items[0]?.parsed?.x;
            return typeof v === 'number' ? formatEpochFull(v) : '';
          },
        },
      },
      zoom: {
        pan: { enabled: true, mode: 'x' },
        zoom: {
          wheel: { enabled: true },
          pinch: { enabled: true },
          mode: 'x',
        },
        limits: zoomLimits,
      },
      ...({
        [TRADE_MARKERS_PLUGIN_ID]: {
          entryMs: showTradeMarkers ? entryMs : null,
          exitMs: showTradeMarkers ? exitMs : null,
          entryColor: theme.entryMarkerColor,
          exitColor: theme.exitMarkerColor,
          labelColor: theme.axisLabelColor,
          outOfRangeFill: theme.outOfRangeFill,
        } satisfies TradeMarkersOptions,
      } as Record<string, TradeMarkersOptions>),
    },
    scales: {
      x: xScale,
      y: {
        ticks: { color: theme.tickColor },
        grid: { color: theme.gridColor },
        title: plot.y_axis_label
          ? { display: true, text: plot.y_axis_label, color: theme.axisLabelColor }
          : undefined,
      },
    },
  };
}

type XScaleOptions = NonNullable<ChartOptions<'line'>['scales']>['x'];

function buildRealtimeScale(theme: ChartTheme): XScaleOptions {
  return {
    type: 'realtime',
    realtime: {
      duration: LIVE_WINDOW_MS,
      refresh: LIVE_REFRESH_MS,
      delay: LIVE_DELAY_MS,
      frameRate: LIVE_FRAME_RATE,
      pause: false,
    },
    ticks: { color: theme.tickColor, maxTicksLimit: 10 },
    grid: { color: theme.gridColor },
    // The streaming plugin advances time itself; we don't need a custom tick callback.
  } as XScaleOptions;
}

function buildHistoricalScale(
  theme: ChartTheme,
  entryMs: number | null,
  exitMs: number | null,
): XScaleOptions {
  const padding = CLOSED_TRADE_PADDING_MS;
  const min = entryMs !== null ? entryMs - padding : undefined;
  const max = exitMs !== null ? exitMs + padding : undefined;
  return {
    type: 'time',
    min,
    max,
    ticks: { color: theme.tickColor, maxTicksLimit: 10 },
    grid: { color: theme.gridColor },
  } as XScaleOptions;
}

function buildZoomLimits(
  entryMs: number | null,
  exitMs: number | null,
): { x: { min: number | 'original'; max: number | 'original' } } | undefined {
  if (entryMs === null || exitMs === null) return undefined;
  const padding = CLOSED_TRADE_PADDING_MS * 4;
  return {
    x: {
      min: entryMs - padding,
      max: exitMs + padding,
    },
  };
}

export function formatEpochTime(ms: number): string {
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return String(ms);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatEpochFull(ms: number): string {
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

export function toEpochMs(iso: string | null): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

export { TRADE_MARKERS_PLUGIN_ID };
