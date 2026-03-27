import { Component, inject } from '@angular/core';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  template: `
    @for (toast of toastService.toasts(); track toast.id) {
      <div
        class="flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border backdrop-blur-sm text-sm animate-slide-in"
        [class]="toastClasses(toast.type)">
        <span class="shrink-0">{{ toastIcon(toast.type) }}</span>
        <span class="flex-1">{{ toast.message }}</span>
        <button (click)="toastService.dismiss(toast.id)" class="text-fg/60 hover:text-fg shrink-0">&times;</button>
      </div>
    }
  `,
  host: {
    class: 'fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none [&>*]:pointer-events-auto',
  },
  styles: [`
    @keyframes slide-in {
      from { opacity: 0; transform: translateY(1rem); }
      to { opacity: 1; transform: translateY(0); }
    }
    .animate-slide-in {
      animation: slide-in 0.2s ease-out;
    }
  `],
})
export class ToastComponent {
  toastService = inject(ToastService);

  toastClasses(type: string): string {
    switch (type) {
      case 'success': return 'bg-positive/90 border-positive/50 text-white';
      case 'error': return 'bg-negative/90 border-negative/50 text-white';
      default: return 'bg-elevated/90 border-edge text-fg';
    }
  }

  toastIcon(type: string): string {
    switch (type) {
      case 'success': return '\u2713';
      case 'error': return '\u2717';
      default: return '\u2139';
    }
  }
}
