import { Routes } from '@angular/router';

const masterDataChildren: Routes = [
  { path: '', redirectTo: 'assets', pathMatch: 'full' },
  { path: 'assets', loadComponent: () => import('./components/assets/asset-list.component').then(m => m.AssetListComponent) },
  { path: 'assets/:id', loadComponent: () => import('./components/assets/asset-detail/asset-detail.component').then(m => m.AssetDetailComponent) },
  { path: 'instruments', loadComponent: () => import('./components/instruments/instrument-list.component').then(m => m.InstrumentListComponent) },
  { path: 'instruments/:id', loadComponent: () => import('./components/instruments/instrument-detail/instrument-detail.component').then(m => m.InstrumentDetailComponent) },
  { path: 'composites', loadComponent: () => import('./components/composites/composite-list.component').then(m => m.CompositeListComponent) },
  { path: 'composites/:id', loadComponent: () => import('./components/composites/composite-detail/composite-detail.component').then(m => m.CompositeDetailComponent) },
  { path: 'providers', loadComponent: () => import('./components/providers/provider-list.component').then(m => m.ProviderListComponent) },
  { path: 'providers/:id', loadComponent: () => import('./components/providers/provider-detail/provider-detail.component').then(m => m.ProviderDetailComponent) },
];

const typesChildren: Routes = [
  { path: '', redirectTo: 'asset-types', pathMatch: 'full' },
  { path: 'asset-types', loadComponent: () => import('./components/settings/asset-type-list.component').then(m => m.AssetTypeListComponent) },
  { path: 'asset-types/:id', loadComponent: () => import('./components/settings/asset-type-detail/asset-type-detail.component').then(m => m.AssetTypeDetailComponent) },
  { path: 'provider-types', loadComponent: () => import('./components/settings/provider-type-list.component').then(m => m.ProviderTypeListComponent) },
  { path: 'provider-types/:id', loadComponent: () => import('./components/settings/provider-type-detail/provider-type-detail.component').then(m => m.ProviderTypeDetailComponent) },
  { path: 'instrument-types', loadComponent: () => import('./components/settings/instrument-type-list.component').then(m => m.InstrumentTypeListComponent) },
  { path: 'instrument-types/:id', loadComponent: () => import('./components/settings/instrument-type-detail/instrument-type-detail.component').then(m => m.InstrumentTypeDetailComponent) },
  { path: 'composite-types', loadComponent: () => import('./components/settings/composite-type-list.component').then(m => m.CompositeTypeListComponent) },
  { path: 'composite-types/:id', loadComponent: () => import('./components/settings/composite-type-detail/composite-type-detail.component').then(m => m.CompositeTypeDetailComponent) },
  { path: 'metadata-types', loadComponent: () => import('./components/settings/metadata-type-list.component').then(m => m.MetadataTypeListComponent) },
  { path: 'metadata-types/:id', loadComponent: () => import('./components/settings/metadata-type-detail/metadata-type-detail.component').then(m => m.MetadataTypeDetailComponent) },
  { path: 'attributes', loadComponent: () => import('./components/settings/attribute-list.component').then(m => m.AttributeListComponent) },
  { path: 'attributes/:id', loadComponent: () => import('./components/settings/attribute-detail/attribute-detail.component').then(m => m.AttributeDetailComponent) },
];

export const routes: Routes = [
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: 'dashboard', loadComponent: () => import('./components/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: 'feeds', loadComponent: () => import('./components/feeds/feed-list.component').then(m => m.FeedListComponent) },
  { path: 'feeds/:id/runs/:runId', loadComponent: () => import('./components/feeds/feed-run-detail/feed-run-detail.component').then(m => m.FeedRunDetailComponent) },
  { path: 'feeds/:id', loadComponent: () => import('./components/feeds/feed-detail/feed-detail.component').then(m => m.FeedDetailComponent) },
  { path: 'strategies', loadComponent: () => import('./components/strategies/strategy-list.component').then(m => m.StrategyListComponent) },
  { path: 'strategies/:id/runs/:runId', loadComponent: () => import('./components/strategies/strategy-run-detail/strategy-run-detail.component').then(m => m.StrategyRunDetailComponent) },
  { path: 'strategies/:id', loadComponent: () => import('./components/strategies/strategy-detail/strategy-detail.component').then(m => m.StrategyDetailComponent) },
  { path: 'exchanges', loadComponent: () => import('./components/exchanges/exchange-list.component').then(m => m.ExchangeListComponent) },
  { path: 'exchanges/:id', loadComponent: () => import('./components/exchanges/exchange-detail/exchange-detail.component').then(m => m.ExchangeDetailComponent) },
  { path: 'trades', loadComponent: () => import('./components/trades/trade-list.component').then(m => m.TradeListComponent) },
  { path: 'data', loadComponent: () => import('./components/data-explorer/data-explorer.component').then(m => m.DataExplorerComponent) },
  { path: 'trades/:tradeId', loadComponent: () => import('./components/trade-detail/trade-detail.component').then(m => m.TradeDetailComponent) },

  // ─── Settings: nested under SettingsLayoutComponent (sub-sidebar) ───────
  {
    path: 'settings',
    loadComponent: () => import('./components/settings/settings-layout.component').then(m => m.SettingsLayoutComponent),
    children: [
      { path: '', redirectTo: 'master-data/assets', pathMatch: 'full' },
      { path: 'master-data', children: masterDataChildren },
      { path: 'types', children: typesChildren },
      { path: 'about', loadComponent: () => import('./components/about/about.component').then(m => m.AboutComponent) },
    ],
  },

  // ─── Back-compat redirects from the old /settings/* tree ────────────────
  { path: 'settings/assets', redirectTo: '/settings/master-data/assets', pathMatch: 'full' },
  { path: 'settings/assets/:id', redirectTo: '/settings/master-data/assets/:id' },
  { path: 'settings/instruments', redirectTo: '/settings/master-data/instruments', pathMatch: 'full' },
  { path: 'settings/instruments/:id', redirectTo: '/settings/master-data/instruments/:id' },
  { path: 'settings/composites', redirectTo: '/settings/master-data/composites', pathMatch: 'full' },
  { path: 'settings/composites/:id', redirectTo: '/settings/master-data/composites/:id' },
  { path: 'settings/providers', redirectTo: '/settings/master-data/providers', pathMatch: 'full' },
  { path: 'settings/providers/:id', redirectTo: '/settings/master-data/providers/:id' },
  { path: 'settings/asset-types', redirectTo: '/settings/types/asset-types', pathMatch: 'full' },
  { path: 'settings/asset-types/:id', redirectTo: '/settings/types/asset-types/:id' },
  { path: 'settings/provider-types', redirectTo: '/settings/types/provider-types', pathMatch: 'full' },
  { path: 'settings/provider-types/:id', redirectTo: '/settings/types/provider-types/:id' },
  { path: 'settings/instrument-types', redirectTo: '/settings/types/instrument-types', pathMatch: 'full' },
  { path: 'settings/instrument-types/:id', redirectTo: '/settings/types/instrument-types/:id' },
  { path: 'settings/composite-types', redirectTo: '/settings/types/composite-types', pathMatch: 'full' },
  { path: 'settings/composite-types/:id', redirectTo: '/settings/types/composite-types/:id' },
  { path: 'settings/metadata-types', redirectTo: '/settings/types/metadata-types', pathMatch: 'full' },
  { path: 'settings/metadata-types/:id', redirectTo: '/settings/types/metadata-types/:id' },
  { path: 'settings/attributes', redirectTo: '/settings/types/attributes', pathMatch: 'full' },
  { path: 'settings/attributes/:id', redirectTo: '/settings/types/attributes/:id' },
];
