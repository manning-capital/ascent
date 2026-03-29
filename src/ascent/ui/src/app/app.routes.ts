import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: 'dashboard', loadComponent: () => import('./components/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: 'feeds', loadComponent: () => import('./components/feeds/feed-list.component').then(m => m.FeedListComponent) },
  { path: 'feeds/:id', loadComponent: () => import('./components/feeds/feed-detail/feed-detail.component').then(m => m.FeedDetailComponent) },
  { path: 'strategies', loadComponent: () => import('./components/strategies/strategy-list.component').then(m => m.StrategyListComponent) },
  { path: 'strategies/:id', loadComponent: () => import('./components/strategies/strategy-detail/strategy-detail.component').then(m => m.StrategyDetailComponent) },
  { path: 'exchanges', loadComponent: () => import('./components/exchanges/exchange-list.component').then(m => m.ExchangeListComponent) },
  { path: 'exchanges/:id', loadComponent: () => import('./components/exchanges/exchange-detail/exchange-detail.component').then(m => m.ExchangeDetailComponent) },
  { path: 'trades', loadComponent: () => import('./components/trades/trade-list.component').then(m => m.TradeListComponent) },
  { path: 'trades/:tradeId', loadComponent: () => import('./components/trade-detail/trade-detail.component').then(m => m.TradeDetailComponent) },
  {
    path: 'settings',
    loadComponent: () => import('./components/settings/settings-layout.component').then(m => m.SettingsLayoutComponent),
    children: [
      { path: '', redirectTo: 'assets', pathMatch: 'full' },
      { path: 'assets', loadComponent: () => import('./components/assets/asset-list.component').then(m => m.AssetListComponent) },
      { path: 'assets/:id', loadComponent: () => import('./components/assets/asset-detail/asset-detail.component').then(m => m.AssetDetailComponent) },
      { path: 'asset-groups/:id', loadComponent: () => import('./components/assets/asset-group-detail/asset-group-detail.component').then(m => m.AssetGroupDetailComponent) },
      { path: 'providers', loadComponent: () => import('./components/providers/provider-list.component').then(m => m.ProviderListComponent) },
      { path: 'providers/:id', loadComponent: () => import('./components/providers/provider-detail/provider-detail.component').then(m => m.ProviderDetailComponent) },
      { path: 'asset-types', loadComponent: () => import('./components/settings/asset-type-list.component').then(m => m.AssetTypeListComponent) },
      { path: 'asset-types/:id', loadComponent: () => import('./components/settings/asset-type-detail/asset-type-detail.component').then(m => m.AssetTypeDetailComponent) },
      { path: 'provider-types', loadComponent: () => import('./components/settings/provider-type-list.component').then(m => m.ProviderTypeListComponent) },
      { path: 'provider-types/:id', loadComponent: () => import('./components/settings/provider-type-detail/provider-type-detail.component').then(m => m.ProviderTypeDetailComponent) },
      { path: 'metadata-types', loadComponent: () => import('./components/settings/metadata-type-list.component').then(m => m.MetadataTypeListComponent) },
      { path: 'metadata-types/:id', loadComponent: () => import('./components/settings/metadata-type-detail/metadata-type-detail.component').then(m => m.MetadataTypeDetailComponent) },
      { path: 'attributes', loadComponent: () => import('./components/settings/attribute-list.component').then(m => m.AttributeListComponent) },
      { path: 'attributes/:id', loadComponent: () => import('./components/settings/attribute-detail/attribute-detail.component').then(m => m.AttributeDetailComponent) },
      { path: 'about', loadComponent: () => import('./components/about/about.component').then(m => m.AboutComponent) },
    ]
  },
];
