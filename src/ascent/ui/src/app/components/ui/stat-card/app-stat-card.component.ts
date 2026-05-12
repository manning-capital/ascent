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
export class AppStatCardComponent {
  label = input.required<string>();
  value = input.required<string>();
  subtitle = input<string>('');
  valueClass = input<string>('');
  size = input<'lg' | 'md' | 'sm'>('md');
  variant = input<'card' | 'flat'>('card');
  align = input<'left' | 'center'>('left');

  alignClass = computed(() => (this.align() === 'center' ? 'text-center' : ''));

  labelClass = computed(
    () => 'text-[10px] font-medium text-fg-muted uppercase tracking-wider mb-0.5',
  );

  valueClasses = computed(() => {
    const sizeMap = {
      lg: 'text-xl font-semibold tabular-nums',
      md: 'text-base font-semibold tabular-nums',
      sm: 'text-sm font-semibold tabular-nums',
    };
    return [sizeMap[this.size()], this.valueClass()].filter(Boolean).join(' ');
  });

  subtitleClass = computed(() => 'text-[11px] text-fg-faint mt-0.5');
}
