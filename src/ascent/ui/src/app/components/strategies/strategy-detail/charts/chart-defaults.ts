import { computed, inject, Signal } from '@angular/core';
import { ChartTokensService } from '../../../ui/chart-canvas/chart-tokens.service';

export interface ChartTheme {
  tickColor: string;
  gridColor: string;
  labelColor: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipTitle: string;
  tooltipBody: string;
  positive: string;
  negative: string;
  info: string;
  warning: string;
  positiveFill: string;
  negativeFill: string;
  infoFill: string;
}

/**
 * Resolves Chart.js theme values from PrimeNG semantic tokens. Re-evaluates
 * when ThemeService toggles, so charts re-render with the new palette
 * without the consumer wiring up listeners.
 */
export function useChartTheme(): Signal<ChartTheme> {
  const tokens = inject(ChartTokensService);
  return computed<ChartTheme>(() => {
    const t = tokens.tokens();
    return {
      tickColor: t.fgMuted,
      gridColor: t.edgeDim,
      labelColor: t.fgMuted,
      tooltipBg: t.surface,
      tooltipBorder: t.edge,
      tooltipTitle: t.fg,
      tooltipBody: t.fgMuted,
      positive: t.positive,
      negative: t.negative,
      info: t.info,
      warning: t.warning,
      positiveFill: withAlpha(t.positive, 0.1),
      negativeFill: withAlpha(t.negative, 0.1),
      infoFill: withAlpha(t.info, 0.1),
    };
  });
}

/**
 * Compact USD-tick formatter for chart axes.
 *
 *   1234567   →  "$1.2M"
 *   12345     →  "$12.3K"
 *   12.345    →  "$12.35"
 *   0.345     →  "$0.35"
 *   0.0001234 →  "$1.2e-4"
 *   0         →  "$0"
 *
 * Chart.js tick callbacks pass numeric `value` through (typed as
 * number | string), so we accept both. */
export function formatPnlTick(value: number | string): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '';
  if (n === 0) return '$0';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1000) {
    return sign + '$' + new Intl.NumberFormat('en', {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(abs);
  }
  if (abs >= 0.01) {
    return sign + '$' + abs.toFixed(2);
  }
  // Tiny values → scientific notation, e.g. 1.2e-4
  return sign + '$' + abs.toExponential(1);
}

/**
 * Convert a hex / rgb / hsl color string to rgba with the given alpha.
 * Falls back to the original value if format is unknown — Chart.js
 * accepts most CSS color strings so a passthrough is safe.
 */
export function withAlpha(color: string, alpha: number): string {
  if (!color) return color;
  const trimmed = color.trim();
  if (trimmed.startsWith('#')) {
    const hex = trimmed.slice(1);
    const expanded = hex.length === 3
      ? hex.split('').map((c) => c + c).join('')
      : hex.length === 8 ? hex.slice(0, 6) : hex;
    if (expanded.length !== 6) return trimmed;
    const num = parseInt(expanded, 16);
    if (Number.isNaN(num)) return trimmed;
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  if (trimmed.startsWith('rgb(') || trimmed.startsWith('hsl(')) {
    return trimmed.replace(/\)$/, ` / ${alpha})`).replace(/^rgb\(/, 'rgba(').replace(/^hsl\(/, 'hsla(');
  }
  return trimmed;
}
