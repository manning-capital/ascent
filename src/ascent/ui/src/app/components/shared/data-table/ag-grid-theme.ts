import { computed, type Signal } from '@angular/core';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';
import type { ThemeService } from '../../../services/theme.service';

ModuleRegistry.registerModules([AllCommunityModule]);

// Aligned to PrimeNG Aura theme tokens:
// Light: slate neutrals (surface.0 = #ffffff, surface.100 = #f1f5f9, surface.200 = #e2e8f0, surface.700 = #334155)
// Dark:  zinc neutrals  (surface.900 = #18181b, surface.800 = #27272a, surface.700 = #3f3f46, surface.400 = #a1a1aa)
export const AG_GRID_THEME = themeQuartz
  .withParams(
    {
      backgroundColor: '#ffffff',        // surface.0  — content.background
      foregroundColor: '#334155',         // surface.700 — text.color
      headerBackgroundColor: '#ffffff',   // surface.0  — same as content (Aura pattern)
      headerTextColor: '#64748b',         // surface.500 — text.muted.color
      borderColor: '#e2e8f0',            // surface.200 — datatable.border.color
      columnBorder: false,               // no vertical column dividers (matches Aura)
      headerColumnBorder: false,
      wrapperBorder: false,              // container div provides the outer border
      accentColor: '#3b82f6',
      oddRowBackgroundColor: '#f8fafc',    // surface.50  — subtle zebra stripe
      rowHoverColor: '#f1f5f9',          // surface.100 — content.hover.background
      browserColorScheme: 'light',
    },
    'light',
  )
  .withParams(
    {
      backgroundColor: '#18181b',        // surface.900 — content.background
      foregroundColor: '#fafafa',         // surface.0   — text.color
      headerBackgroundColor: '#18181b',   // surface.900 — same as content (Aura pattern)
      headerTextColor: '#a1a1aa',         // surface.400 — text.muted.color
      borderColor: '#3f3f46',            // surface.700 — datatable.border.color
      columnBorder: false,
      headerColumnBorder: false,
      wrapperBorder: false,
      accentColor: '#3b82f6',
      oddRowBackgroundColor: '#1c1c1f',    // ~surface.850 — subtle zebra stripe
      rowHoverColor: '#27272a',          // surface.800 — content.hover.background
      browserColorScheme: 'dark',
    },
    'dark',
  );

export function agThemeMode(themeService: ThemeService): Signal<string> {
  return computed(() => (themeService.isDark() ? 'dark' : 'light'));
}
