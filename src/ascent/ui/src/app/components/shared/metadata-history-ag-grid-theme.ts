import { computed, type Signal } from '@angular/core';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';
import type { ThemeService } from '../../services/theme.service';

ModuleRegistry.registerModules([AllCommunityModule]);

// Aligned to Ascent's flat palette (canvas == surface; borders define regions).
// Zebra stripe disabled and hover uses a low-alpha overlay so the grid
// matches the rest of the UI.
export const AG_GRID_THEME = themeQuartz
  .withParams(
    {
      backgroundColor: '#ffffff',
      foregroundColor: '#16161e',
      headerBackgroundColor: '#ffffff',
      headerTextColor: '#6b6b76',
      borderColor: 'rgba(0, 0, 0, 0.08)',
      columnBorder: false,
      headerColumnBorder: false,
      wrapperBorder: false,
      accentColor: '#6366f1',
      oddRowBackgroundColor: '#ffffff',
      rowHoverColor: 'rgba(0, 0, 0, 0.03)',
      browserColorScheme: 'light',
    },
    'light',
  )
  .withParams(
    {
      backgroundColor: '#0d0d12',
      foregroundColor: '#e4e4eb',
      headerBackgroundColor: '#0d0d12',
      headerTextColor: '#9494a0',
      borderColor: 'rgba(255, 255, 255, 0.08)',
      columnBorder: false,
      headerColumnBorder: false,
      wrapperBorder: false,
      accentColor: '#818cf8',
      oddRowBackgroundColor: '#0d0d12',
      rowHoverColor: 'rgba(255, 255, 255, 0.04)',
      browserColorScheme: 'dark',
    },
    'dark',
  );

export function agThemeMode(themeService: ThemeService): Signal<string> {
  return computed(() => (themeService.isDark() ? 'dark' : 'light'));
}
