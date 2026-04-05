import { Component, computed, input } from '@angular/core';
import { Tag } from 'primeng/tag';

@Component({
  selector: 'app-badge',
  standalone: true,
  imports: [Tag],
  template: `
    <p-tag [value]="label()" [severity]="severity()" [rounded]="true" />
  `,
})
export class BadgeComponent {
  label = input.required<string>();
  variant = input<'status' | 'side' | 'tag'>('tag');

  severity = computed<'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' | undefined>(() => {
    const label = this.label().toUpperCase();

    if (this.variant() === 'status') {
      if (label === 'OPEN' || label === 'FILLED') return 'success';
      if (label === 'OPENING' || label === 'CLOSING' || label === 'PARTIALLY_FILLED') return 'contrast';
      if (label === 'PENDING' || label === 'SUBMITTED' || label === 'ACCEPTED') return 'warn';
      if (label === 'ERROR' || label === 'REJECTED') return 'danger';
      if (label === 'CLOSED' || label === 'CANCELLED') return 'secondary';
      return 'warn';
    }

    switch (label) {
      case 'LONG':
      case 'ENTRY':
      case 'COMPLETED':
      case 'BUY':
        return 'success';
      case 'SHORT':
      case 'FAILED':
      case 'STOP_LOSS':
      case 'SELL':
        return 'danger';
      case 'COMPOUND':
      case 'RUNNING':
      case 'TAKE_PROFIT':
        return 'warn';
      case 'PAPER':
      case 'EXIT':
        return 'contrast';
      case 'PENDING':
      case 'CLOSED':
        return 'secondary';
      default:
        return 'secondary';
    }
  });
}
