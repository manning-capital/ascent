import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ICellRendererParams } from 'ag-grid-community';

// ─── Severity → color mapping (matches PrimeNG Aura palette) ─
const SEVERITY_COLORS: Record<string, { bg: string; text: string }> = {
  success:   { bg: 'rgba(34,197,94,0.15)',  text: '#22c55e' },
  danger:    { bg: 'rgba(239,68,68,0.15)',  text: '#ef4444' },
  warn:      { bg: 'rgba(249,115,22,0.15)', text: '#f97316' },
  info:      { bg: 'rgba(59,130,246,0.15)', text: '#3b82f6' },
  secondary: { bg: 'rgba(161,161,170,0.15)', text: '#a1a1aa' },
  contrast:  { bg: 'rgba(250,250,250,0.1)', text: '#fafafa' },
};

function badgeStyles(severity: string): string {
  const c = SEVERITY_COLORS[severity] ?? SEVERITY_COLORS['secondary'];
  return `display:inline-flex;align-items:center;padding:2px 8px;border-radius:9999px;font-size:0.7rem;font-weight:600;line-height:1.4;white-space:nowrap;background:${c.bg};color:${c.text}`;
}

// ─── Status cell renderer (Active/Inactive boolean badge) ────
@Component({
  selector: 'ag-status-cell',
  standalone: true,
  template: `<span [style]="styles">{{ label }}</span>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class StatusCellRenderer implements ICellRendererAngularComp {
  label = '';
  styles = '';
  private tagMapper?: (value: any, row: any) => { label: string; severity: string };

  agInit(params: ICellRendererParams & { tagMapper?: any }): void {
    this.tagMapper = params.tagMapper;
    this.update(params);
  }

  refresh(params: ICellRendererParams & { tagMapper?: any }): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    if (this.tagMapper) {
      const result = this.tagMapper(params.value, params.data);
      this.label = result.label;
      this.styles = badgeStyles(result.severity);
    } else {
      this.label = params.value ? 'Active' : 'Inactive';
      this.styles = badgeStyles(params.value ? 'success' : 'secondary');
    }
  }
}

// ─── Tag cell renderer (generic badge with custom mapper) ────
@Component({
  selector: 'ag-tag-cell',
  standalone: true,
  template: `@if (label) { <span [style]="styles">{{ label }}</span> }`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class TagCellRenderer implements ICellRendererAngularComp {
  label = '';
  styles = '';
  private tagMapper?: (value: any, row: any) => { label: string; severity: string };

  agInit(params: ICellRendererParams & { tagMapper?: any }): void {
    this.tagMapper = params.tagMapper;
    this.update(params);
  }

  refresh(params: ICellRendererParams & { tagMapper?: any }): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    if (this.tagMapper) {
      const result = this.tagMapper(params.value, params.data);
      this.label = result.label;
      this.styles = badgeStyles(result.severity);
    } else {
      this.label = params.value ?? '';
      this.styles = badgeStyles('secondary');
    }
  }
}

// ─── Link cell renderer (routerLink that stops row-click propagation) ─
@Component({
  selector: 'ag-link-cell',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (route) {
      <a [routerLink]="route" (click)="$event.stopPropagation()" class="text-primary hover:underline">{{ text }}</a>
    } @else {
      {{ text }}
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class LinkCellRenderer implements ICellRendererAngularComp {
  text = '';
  route: string | any[] | null = null;
  private linkRoute?: (row: any) => string | any[];

  agInit(params: ICellRendererParams & { linkRoute?: any }): void {
    this.linkRoute = params.linkRoute;
    this.update(params);
  }

  refresh(params: ICellRendererParams & { linkRoute?: any }): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    this.text = params.value ?? '';
    this.route = this.linkRoute && params.data ? this.linkRoute(params.data) : null;
  }
}

// ─── Currency cell renderer (USD with green/red coloring) ────
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
});

@Component({
  selector: 'ag-currency-cell',
  standalone: true,
  template: `<span [class]="colorClass">{{ formatted }}</span>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class CurrencyCellRenderer implements ICellRendererAngularComp {
  formatted = '';
  colorClass = '';

  agInit(params: ICellRendererParams): void {
    this.update(params);
  }

  refresh(params: ICellRendererParams): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    const val = params.value;
    if (val == null) {
      this.formatted = '';
      this.colorClass = '';
      return;
    }
    const num = Number(val);
    this.formatted = currencyFormatter.format(num);
    this.colorClass = num > 0 ? 'text-green-500' : num < 0 ? 'text-red-500' : '';
  }
}

// ─── Exported helper for custom renderers in other components ─
export { badgeStyles, SEVERITY_COLORS };
