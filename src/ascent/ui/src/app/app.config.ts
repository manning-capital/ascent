import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { providePrimeNG } from 'primeng/config';
import { ConfirmationService, MessageService } from 'primeng/api';
import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

import { routes } from './app.routes';

const AscentPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#f0fdfa',
      100: '#ccfbf1',
      200: '#99f6e4',
      300: '#5eead4',
      400: '#2dd4bf',
      500: '#14b8a6',
      600: '#0d9488',
      700: '#0f766e',
      800: '#115e59',
      900: '#134e4a',
      950: '#042f2e',
    },
    colorScheme: {
      light: {
        content: {
          background: '#ffffff',
          hoverBackground: 'rgba(0, 0, 0, 0.03)',
          borderColor: 'rgba(0, 0, 0, 0.08)',
        },
        sidebar: {
          background: '#f6f6f8',
        },
        positive: {
          color: '#16a34a',
          contrastColor: '#ffffff',
          hoverColor: '#15803d',
          activeColor: '#166534',
        },
        negative: {
          color: '#dc2626',
          contrastColor: '#ffffff',
          hoverColor: '#b91c1c',
          activeColor: '#991b1b',
        },
        warning: {
          color: '#ea580c',
          contrastColor: '#ffffff',
          hoverColor: '#c2410c',
          activeColor: '#9a3412',
        },
        info: {
          color: '#2563eb',
          contrastColor: '#ffffff',
          hoverColor: '#1d4ed8',
          activeColor: '#1e40af',
        },
        graphAccent: {
          1: '#6366f1',
          2: '#14b8a6',
          3: '#f97316',
          4: '#eab308',
          5: '#ec4899',
        },
      },
      dark: {
        content: {
          background: '#0d0d12',
          hoverBackground: 'rgba(255, 255, 255, 0.04)',
          borderColor: 'rgba(255, 255, 255, 0.08)',
        },
        sidebar: {
          background: '#08080c',
        },
        positive: {
          color: '#22c55e',
          contrastColor: '#052e16',
          hoverColor: '#16a34a',
          activeColor: '#15803d',
        },
        negative: {
          color: '#ef4444',
          contrastColor: '#450a0a',
          hoverColor: '#dc2626',
          activeColor: '#b91c1c',
        },
        warning: {
          color: '#f97316',
          contrastColor: '#431407',
          hoverColor: '#ea580c',
          activeColor: '#c2410c',
        },
        info: {
          color: '#3b82f6',
          contrastColor: '#172554',
          hoverColor: '#2563eb',
          activeColor: '#1d4ed8',
        },
        graphAccent: {
          1: '#818cf8',
          2: '#2dd4bf',
          3: '#fb923c',
          4: '#facc15',
          5: '#f472b6',
        },
      },
    },
  },
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(),
    MessageService,
    ConfirmationService,
    providePrimeNG({
      theme: {
        preset: AscentPreset,
        options: {
          darkModeSelector: '.dark',
          cssLayer: {
            name: 'primeng',
            order: 'tw-base, primeng, tw-utilities',
          },
        },
      },
    }),
  ]
};
