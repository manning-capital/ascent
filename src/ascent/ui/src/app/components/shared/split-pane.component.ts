import { Component, signal, HostListener, ElementRef, ViewChild } from '@angular/core';

@Component({
  selector: 'app-split-pane',
  standalone: true,
  template: `
    <div #container class="flex h-full w-full overflow-hidden">
      <!-- Left pane -->
      <div class="overflow-hidden" [style.width.%]="splitPercent()">
        <ng-content select="[left]"/>
      </div>

      <!-- Drag handle -->
      <div
        class="w-1.5 shrink-0 cursor-col-resize bg-fg/5 hover:bg-info/40 active:bg-info/60 transition-colors relative group"
        (mousedown)="onDragStart($event)">
        <div class="absolute inset-y-0 -left-1 -right-1"></div>
      </div>

      <!-- Right pane -->
      <div class="overflow-hidden flex-1">
        <ng-content select="[right]"/>
      </div>
    </div>
  `,
})
export class SplitPaneComponent {
  @ViewChild('container') containerRef!: ElementRef<HTMLElement>;

  splitPercent = signal(60);
  private dragging = false;

  onDragStart(e: MouseEvent): void {
    e.preventDefault();
    this.dragging = true;
  }

  @HostListener('window:mousemove', ['$event'])
  onDragMove(e: MouseEvent): void {
    if (!this.dragging || !this.containerRef) return;
    const rect = this.containerRef.nativeElement.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    this.splitPercent.set(Math.min(85, Math.max(25, pct)));
  }

  @HostListener('window:mouseup')
  onDragEnd(): void {
    this.dragging = false;
  }
}
