import { Component } from '@angular/core';
import { ProgressSpinner } from 'primeng/progressspinner';

@Component({
  selector: 'app-loading',
  standalone: true,
  imports: [ProgressSpinner],
  template: `
    <div class="flex items-center justify-center py-12">
      <p-progressSpinner strokeWidth="3" animationDuration="1s" />
    </div>
  `,
})
export class LoadingSpinnerComponent {}
