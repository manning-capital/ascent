import { Component, input, output } from '@angular/core';
import { Splitter, SplitterResizeEndEvent } from 'primeng/splitter';
import { WorkspaceStorageService } from './workspace-storage.service';

/**
 * Thin wrapper around p-splitter that persists panel sizes to localStorage.
 *
 * For 2- or 3-panel detail workspaces. For complex nested splits, use
 * p-splitter directly and inject WorkspaceStorageService to handle
 * load/save manually.
 *
 *   <app-workspace storageKey="strategy-detail-top" layout="horizontal" [defaultSizes]="[60, 40]">
 *     <ng-template #panels>
 *       <div>Left content</div>
 *       <div>Right content</div>
 *     </ng-template>
 *   </app-workspace>
 *
 * Children are projected directly into the splitter's content slot.
 */
@Component({
  selector: 'app-workspace',
  standalone: true,
  imports: [Splitter],
  host: { class: 'flex h-full w-full' },
  template: `
    <p-splitter
      [layout]="layout()"
      [panelSizes]="initialSizes"
      [minSizes]="minSizes()"
      styleClass="h-full w-full border-0 bg-transparent"
      (onResizeEnd)="onResizeEnd($event)"
    >
      <ng-content />
    </p-splitter>
  `,
})
export class AppWorkspaceComponent {
  storageKey = input.required<string>();
  layout = input<'horizontal' | 'vertical'>('horizontal');
  defaultSizes = input<number[]>([]);
  minSizes = input<number[]>([]);

  readonly resized = output<number[]>();

  initialSizes: number[] = [];

  constructor(private storage: WorkspaceStorageService) {
    queueMicrotask(() => {
      const stored = this.storage.read(this.storageKey());
      this.initialSizes = stored && stored.length > 0 ? stored : this.defaultSizes();
    });
  }

  onResizeEnd(event: SplitterResizeEndEvent): void {
    const sizes = event.sizes.map((s) => (typeof s === 'number' ? s : Number(s)));
    this.storage.save(this.storageKey(), sizes);
    this.resized.emit(sizes);
  }
}
