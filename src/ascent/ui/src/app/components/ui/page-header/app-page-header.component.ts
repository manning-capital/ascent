import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

export interface AppBreadcrumbItem {
  label: string;
  routerLink?: string | any[];
}

@Component({
  selector: 'app-page-header',
  standalone: true,
  imports: [RouterLink],
  template: `
    <header class="flex flex-col gap-2 border-b border-edge px-4 py-2.5">
      @if (breadcrumb()?.length) {
        <nav class="flex items-center gap-1 text-xs text-fg-muted">
          @for (item of breadcrumb(); track item.label; let last = $last) {
            @if (item.routerLink && !last) {
              <a [routerLink]="item.routerLink" class="hover:text-fg transition-colors">
                {{ item.label }}
              </a>
            } @else {
              <span [class.text-fg]="last">{{ item.label }}</span>
            }
            @if (!last) {
              <span class="text-fg-faint" aria-hidden="true">/</span>
            }
          }
        </nav>
      }
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h1 class="text-base font-semibold text-fg leading-tight truncate">
            {{ title() }}
          </h1>
          @if (subtitle()) {
            <p class="text-xs text-fg-muted mt-0.5 truncate">{{ subtitle() }}</p>
          }
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <ng-content select="[actions]" />
        </div>
      </div>
      <ng-content select="[tabs]" />
    </header>
  `,
})
export class AppPageHeaderComponent {
  title = input.required<string>();
  subtitle = input<string | undefined>(undefined);
  breadcrumb = input<AppBreadcrumbItem[] | undefined>(undefined);
}
