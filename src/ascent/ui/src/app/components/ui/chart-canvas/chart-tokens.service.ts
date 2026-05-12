import { Injectable, computed, inject, signal } from '@angular/core';
import { ThemeService } from '../../../services/theme.service';

export interface ChartTokens {
  fg: string;
  fgMuted: string;
  fgFaint: string;
  edge: string;
  edgeDim: string;
  surface: string;
  canvas: string;
  positive: string;
  negative: string;
  warning: string;
  info: string;
  graphAccent1: string;
  graphAccent2: string;
  graphAccent3: string;
  graphAccent4: string;
  graphAccent5: string;
}

const TOKEN_VAR_MAP: Record<keyof ChartTokens, string> = {
  fg: '--fg',
  fgMuted: '--fg-muted',
  fgFaint: '--fg-faint',
  edge: '--edge',
  edgeDim: '--edge-dim',
  surface: '--surface',
  canvas: '--canvas',
  positive: '--positive',
  negative: '--negative',
  warning: '--warning',
  info: '--info',
  graphAccent1: '--graph-accent-1',
  graphAccent2: '--graph-accent-2',
  graphAccent3: '--graph-accent-3',
  graphAccent4: '--graph-accent-4',
  graphAccent5: '--graph-accent-5',
};

/**
 * Resolves Ascent semantic CSS variables to concrete color strings for
 * D3 / Chart.js consumption. Re-reads tokens whenever the theme toggles.
 *
 *   const tokens = chartTokens.tokens();
 *   d3.axisBottom(scale).tickFormat(...).color = tokens.fgMuted;
 *
 * Callers should reference `tokens()` inside `computed()` or `effect()`
 * so theme changes propagate automatically.
 */
@Injectable({ providedIn: 'root' })
export class ChartTokensService {
  private theme = inject(ThemeService);
  private cacheBust = signal(0);

  readonly tokens = computed<ChartTokens>(() => {
    this.theme.isDark();
    this.cacheBust();
    return this.readAll();
  });

  invalidate(): void {
    this.cacheBust.update((n) => n + 1);
  }

  private readAll(): ChartTokens {
    const style = getComputedStyle(document.documentElement);
    const out = {} as ChartTokens;
    for (const key of Object.keys(TOKEN_VAR_MAP) as (keyof ChartTokens)[]) {
      const raw = style.getPropertyValue(TOKEN_VAR_MAP[key]).trim();
      out[key] = raw || '';
    }
    return out;
  }
}
