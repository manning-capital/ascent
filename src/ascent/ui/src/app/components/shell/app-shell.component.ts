import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Drawer } from 'primeng/drawer';
import { AppSidebarComponent } from './app-sidebar.component';

const COLLAPSED_KEY = 'ascent-sidebar-collapsed';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, AppSidebarComponent, Drawer],
  host: { class: 'flex h-screen w-screen overflow-hidden' },
  template: `
    <app-sidebar
      class="hidden md:flex"
      [style.width.px]="collapsed() ? 64 : 232"
      [collapsed]="collapsed()"
      (toggle)="onToggleSidebar()"
    />

    <main class="flex-1 min-w-0 min-h-0 overflow-auto bg-canvas">
      <router-outlet />
    </main>

    <button
      type="button"
      class="md:hidden fixed top-2 left-2 z-50 flex items-center justify-center w-9 h-9 rounded-md bg-canvas border border-edge text-fg-muted hover:bg-edge-dim transition-colors"
      (click)="mobileOpen.set(true)"
      aria-label="Open navigation"
    >
      <i class="pi pi-bars" style="font-size: 1rem;"></i>
    </button>

    <p-drawer
      [(visible)]="mobileOpen"
      position="left"
      [showCloseIcon]="false"
      styleClass="md:hidden"
      [style]="{ width: '240px' }"
    >
      <ng-template pTemplate="content">
        <app-sidebar [collapsed]="false" />
      </ng-template>
    </p-drawer>
  `,
})
export class AppShellComponent {
  collapsed = signal(false);
  mobileOpen = signal(false);

  constructor() {
    try {
      this.collapsed.set(localStorage.getItem(COLLAPSED_KEY) === 'true');
    } catch {
      /* ignore */
    }
  }

  onToggleSidebar(): void {
    this.collapsed.update((c) => {
      const next = !c;
      try { localStorage.setItem(COLLAPSED_KEY, String(next)); } catch {}
      return next;
    });
  }
}
