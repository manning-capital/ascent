import { Component, computed, input } from '@angular/core';
import { Card } from 'primeng/card';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  imports: [Card],
  host: { class: 'flex' },
  template: `
    @if (variant() === 'card') {
      <p-card styleClass="flex-1" [class]="alignClass()">
        <p [class]="labelClass()">{{ label() }}</p>
        <p [class]="valueClasses()">{{ value() }}</p>
        @if (subtitle()) {
          <p [class]="subtitleClass()">{{ subtitle() }}</p>
        }
      </p-card>
    } @else {
      <div [class]="'flex-1 ' + alignClass()">
        <p [class]="labelClass()">{{ label() }}</p>
        <p [class]="valueClasses()">{{ value() }}</p>
        @if (subtitle()) {
          <p [class]="subtitleClass()">{{ subtitle() }}</p>
        }
      </div>
    }
  `,
})
export class StatCardComponent {
  label = input.required<string>();
  value = input.required<string>();
  subtitle = input<string>('');
  valueClass = input<string>('');
  size = input<'lg' | 'md' | 'sm'>('lg');
  variant = input<'card' | 'flat'>('card');
  align = input<'left' | 'center'>('left');

  alignClass = computed(() => {
    return this.align() === 'center' ? 'text-center' : '';
  });

  labelClass = computed(() => {
    return 'text-xs font-medium text-surface-500 uppercase tracking-wider mb-1';
  });

  valueClasses = computed(() => {
    const sizeMap = {
      lg: 'text-2xl font-bold',
      md: 'text-lg font-bold',
      sm: 'text-sm font-semibold',
    };
    return [sizeMap[this.size()], this.valueClass()].filter(Boolean).join(' ');
  });

  subtitleClass = computed(() => {
    return 'text-xs text-surface-400 mt-1';
  });
}
