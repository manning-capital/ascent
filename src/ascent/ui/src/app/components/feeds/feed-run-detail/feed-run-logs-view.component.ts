import { Component } from '@angular/core';
import { AppEmptyStateComponent } from '../../ui/empty-state/app-empty-state.component';

@Component({
  selector: 'app-feed-run-logs-view',
  standalone: true,
  imports: [AppEmptyStateComponent],
  styles: [`
    :host { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  `],
  template: `
    <app-empty-state
      title="Logs coming soon"
      message="Run logs will be available here once execution log capture is wired up."
      icon="inbox"/>
  `,
})
export class FeedRunLogsViewComponent {}
