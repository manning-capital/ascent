import { Component } from '@angular/core';

@Component({
  selector: 'app-loading',
  standalone: true,
  template: `
    <div class="flex items-center justify-center py-12">
      <div class="w-8 h-8 border-2 border-fg-faint border-t-fg rounded-full animate-spin"></div>
    </div>
  `,
})
export class LoadingSpinnerComponent {}
