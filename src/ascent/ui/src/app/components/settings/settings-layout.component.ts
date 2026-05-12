import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

interface SettingsNavItem {
  label: string;
  routerLink: string;
}

interface SettingsNavSection {
  label: string;
  items: SettingsNavItem[];
}

const SETTINGS_NAV: SettingsNavSection[] = [
  {
    label: 'Master Data',
    items: [
      { label: 'Assets', routerLink: 'master-data/assets' },
      { label: 'Instruments', routerLink: 'master-data/instruments' },
      { label: 'Composites', routerLink: 'master-data/composites' },
      { label: 'Providers', routerLink: 'master-data/providers' },
    ],
  },
  {
    label: 'Type System',
    items: [
      { label: 'Asset Types', routerLink: 'types/asset-types' },
      { label: 'Provider Types', routerLink: 'types/provider-types' },
      { label: 'Instrument Types', routerLink: 'types/instrument-types' },
      { label: 'Composite Types', routerLink: 'types/composite-types' },
      { label: 'Metadata Types', routerLink: 'types/metadata-types' },
      { label: 'Attributes', routerLink: 'types/attributes' },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'About', routerLink: 'about' },
    ],
  },
];

@Component({
  selector: 'app-settings-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  host: { class: '!flex-row h-full min-h-0 w-full' },
  template: `
    <aside
      class="hidden md:flex w-52 shrink-0 flex-col border-r border-edge overflow-y-auto py-2"
      style="background: var(--sidebar-bg);"
    >
      @for (section of nav; track section.label; let isFirst = $first) {
        @if (!isFirst) {
          <div class="border-t border-edge mx-3 my-2"></div>
        }
        <div class="px-5 py-1 text-[10px] font-semibold uppercase tracking-wider text-fg-faint">
          {{ section.label }}
        </div>
        @for (item of section.items; track item.label) {
          <a
            [routerLink]="item.routerLink"
            routerLinkActive="!bg-primary/10 !text-primary !font-medium"
            class="flex items-center h-9 mx-3 my-0.5 px-3 rounded-md text-[13px] text-fg-muted hover:bg-edge-dim hover:text-fg transition-colors"
          >
            {{ item.label }}
          </a>
        }
      }
    </aside>

    <div class="flex-1 min-w-0 overflow-y-auto flex flex-col">
      <router-outlet />
    </div>
  `,
})
export class SettingsLayoutComponent {
  readonly nav = SETTINGS_NAV;
}
