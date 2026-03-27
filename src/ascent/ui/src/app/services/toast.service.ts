import { inject, Injectable } from '@angular/core';
import { MessageService } from 'primeng/api';

@Injectable({ providedIn: 'root' })
export class ToastService {
  private messageService = inject(MessageService);

  show(message: string, type: 'success' | 'error' | 'info' = 'info', duration = 3000): void {
    this.messageService.add({
      severity: type === 'error' ? 'error' : type === 'success' ? 'success' : 'info',
      summary: type.charAt(0).toUpperCase() + type.slice(1),
      detail: message,
      life: duration,
    });
  }

  success(message: string): void {
    this.show(message, 'success');
  }

  error(message: string): void {
    this.show(message, 'error', 5000);
  }
}
