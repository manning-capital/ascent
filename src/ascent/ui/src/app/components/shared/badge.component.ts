import { Component, input } from '@angular/core';

@Component({
  selector: 'app-badge',
  standalone: true,
  template: `
    <span [class]="badgeClasses()">{{ label() }}</span>
  `,
})
export class BadgeComponent {
  label = input.required<string>();
  variant = input<'status' | 'side' | 'tag'>('tag');

  badgeClasses(): string {
    const base = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider';
    const label = this.label().toUpperCase();

    if (this.variant() === 'status') {
      if (label === 'OPEN') return `${base} bg-positive/15 text-positive`;
      if (label === 'CLOSED') return `${base} bg-fg-faint/15 text-fg-muted`;
      return `${base} bg-warning/15 text-warning`;
    }

    if (label === 'LONG') return `${base} bg-positive/15 text-positive`;
    if (label === 'SHORT') return `${base} bg-negative/15 text-negative`;
    if (label === 'COMPOUND') return `${base} bg-warning/15 text-warning`;
    if (label === 'PAPER') return `${base} bg-blue-slate/15 text-blue-slate`;

    return `${base} bg-fg-faint/15 text-fg-muted`;
  }
}
