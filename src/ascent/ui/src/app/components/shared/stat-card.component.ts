import { Component, computed, input } from '@angular/core';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  host: { class: 'flex' },
  template: `
    <div [class]="containerClass()">
      <p [class]="labelClass()">{{ label() }}</p>
      <p [class]="valueClasses()">{{ value() }}</p>
      @if (subtitle()) {
        <p [class]="subtitleClass()">{{ subtitle() }}</p>
      }
    </div>
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

  containerClass = computed(() => {
    const classes = ['flex-1'];
    if (this.variant() === 'card') {
      classes.push('rounded-xl border border-edge bg-surface/50 p-5');
    }
    if (this.align() === 'center') {
      classes.push('text-center');
    }
    return classes.join(' ');
  });

  labelClass = computed(() => {
    return 'text-xs font-medium text-fg-muted uppercase tracking-wider mb-1';
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
    return 'text-xs text-fg-faint mt-1';
  });
}
