import { Component, inject, input, output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Tooltip } from 'primeng/tooltip';
import { ThemeService } from '../../services/theme.service';

interface NavItem {
  label: string;
  icon: string;
  routerLink: string;
}

const TOP_NAV_SECTIONS: NavItem[][] = [
  [
    { label: 'Dashboard', icon: 'pi pi-home', routerLink: '/dashboard' },
  ],
  [
    { label: 'Feeds', icon: 'pi pi-wave-pulse', routerLink: '/feeds' },
    { label: 'Strategies', icon: 'pi pi-compass', routerLink: '/strategies' },
    { label: 'Exchanges', icon: 'pi pi-arrows-h', routerLink: '/exchanges' },
  ],
  [
    { label: 'Trades', icon: 'pi pi-chart-line', routerLink: '/trades' },
    { label: 'Data Explorer', icon: 'pi pi-database', routerLink: '/data' },
  ],
];

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [Tooltip, RouterLink, RouterLinkActive],
  host: {
    class: 'flex flex-col h-full w-full border-r border-edge shrink-0 overflow-hidden',
    style: 'background: var(--sidebar-bg);',
  },
  styles: [`
    :host-context(.dark) .ascent-logo {
      filter: invert(1) hue-rotate(180deg);
    }
  `],
  template: `
    <a
      routerLink="/dashboard"
      class="flex items-center gap-2.5 h-14 px-4 shrink-0 border-b border-edge text-fg hover:bg-edge-dim transition-colors"
      [class.justify-center]="collapsed()"
      [class.px-0]="collapsed()"
    >
      @if (collapsed()) {
        <img
          src="ascent-logo.svg"
          alt="Ascent"
          class="block h-10 w-auto ascent-logo"
        />
      } @else {
        <img
          src="ascent-lockup.svg"
          alt="Ascent"
          class="block h-7 w-auto ascent-logo"
        />
      }
    </a>

    <div class="shrink-0 border-b border-edge py-1.5 flex" [class.justify-center]="collapsed()">
      <button
        type="button"
        class="flex items-center justify-center gap-3 h-9 rounded-md text-[13px] text-fg-muted hover:bg-edge-dim hover:text-fg transition-colors"
        [style.width]="collapsed() ? '36px' : 'calc(100% - 1.5rem)'"
        [class.mx-3]="!collapsed()"
        [class.px-3]="!collapsed()"
        (click)="toggle.emit()"
        [pTooltip]="collapsed() ? 'Expand sidebar' : ''"
        tooltipPosition="right"
      >
        <i [class]="collapsed() ? 'pi pi-angle-double-right' : 'pi pi-angle-double-left'" style="font-size: 0.85rem;"></i>
        @if (!collapsed()) {
          <span class="flex-1 text-left">Collapse</span>
        }
      </button>
    </div>

    <nav class="flex-1 min-h-0 overflow-y-auto">
      @for (section of topNavSections; track $index; let isFirst = $first) {
        @if (!isFirst) {
          <div class="border-t border-edge mx-3 my-1"></div>
        }
        @for (item of section; track item.label) {
          <a
            [routerLink]="item.routerLink"
            routerLinkActive="!bg-primary/10 !text-primary !font-medium"
            [routerLinkActiveOptions]="{ exact: false }"
            class="flex items-center gap-3 h-10 my-1.5 rounded-md text-sm text-fg-muted hover:bg-edge-dim hover:text-fg transition-colors"
            [class.mx-2]="collapsed()"
            [class.justify-center]="collapsed()"
            [class.mx-3]="!collapsed()"
            [class.px-3]="!collapsed()"
            [pTooltip]="collapsed() ? item.label : ''"
            tooltipPosition="right"
          >
            <i [class]="item.icon" style="font-size: 1rem;"></i>
            @if (!collapsed()) {
              <span class="truncate">{{ item.label }}</span>
            }
          </a>
        }
      }

      <div class="border-t border-edge mx-3 my-1"></div>
      <a
        routerLink="/settings"
        routerLinkActive="!bg-primary/10 !text-primary !font-medium"
        [routerLinkActiveOptions]="{ exact: false }"
        class="flex items-center gap-3 h-10 my-1.5 rounded-md text-sm text-fg-muted hover:bg-edge-dim hover:text-fg transition-colors"
        [class.mx-2]="collapsed()"
        [class.justify-center]="collapsed()"
        [class.mx-3]="!collapsed()"
        [class.px-3]="!collapsed()"
        [pTooltip]="collapsed() ? 'Settings' : ''"
        tooltipPosition="right"
      >
        <i class="pi pi-cog" style="font-size: 1rem;"></i>
        @if (!collapsed()) {
          <span class="truncate">Settings</span>
        }
      </a>
    </nav>

    <div class="border-t border-edge shrink-0 py-1.5 flex" [class.justify-center]="collapsed()">
      <button
        type="button"
        class="flex items-center justify-center gap-3 h-10 rounded-md text-[13px] text-fg-muted hover:bg-edge-dim hover:text-fg transition-colors"
        [style.width]="collapsed() ? '40px' : 'calc(100% - 1.5rem)'"
        [class.mx-3]="!collapsed()"
        [class.px-3]="!collapsed()"
        (click)="theme.toggle()"
        [pTooltip]="collapsed() ? (theme.isDark() ? 'Light mode' : 'Dark mode') : ''"
        tooltipPosition="right"
      >
        <i [class]="theme.isDark() ? 'pi pi-sun' : 'pi pi-moon'" style="font-size: 0.95rem;"></i>
        @if (!collapsed()) {
          <span class="flex-1 text-left">{{ theme.isDark() ? 'Light mode' : 'Dark mode' }}</span>
        }
      </button>
    </div>
  `,
})
export class AppSidebarComponent {
  collapsed = input(false);
  readonly toggle = output<void>();

  theme = inject(ThemeService);

  readonly topNavSections = TOP_NAV_SECTIONS;
}
