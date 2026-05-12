import { Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CdkDragHandle } from '@angular/cdk/drag-drop';
import { Button } from 'primeng/button';
import { Menu } from 'primeng/menu';
import { InputText } from 'primeng/inputtext';
import type { MenuItem } from 'primeng/api';
import type { CellKind } from '../types';

const KIND_ICONS: Record<CellKind, string> = {
  line: 'pi pi-chart-line',
  bar: 'pi pi-chart-bar',
  scatter: 'pi pi-chart-scatter',
  histogram: 'pi pi-chart-bar',
  table: 'pi pi-table',
};

const KIND_LABELS: Record<CellKind, string> = {
  line: 'Line chart',
  bar: 'Bar chart',
  scatter: 'Scatter',
  histogram: 'Histogram',
  table: 'Table',
};

/** Hairline-bordered card that wraps a chart or table cell. Owns the cell
 *  header (drag handle, kind icon, click-to-edit title, action menu) and
 *  exposes the body via a content slot. */
@Component({
  selector: 'app-data-cell-shell',
  standalone: true,
  imports: [FormsModule, CdkDragHandle, Button, Menu, InputText],
  template: `
    <div class="border border-edge rounded-md bg-surface flex flex-col min-h-0">
      <header class="flex items-center gap-2 px-2 py-1.5 border-b border-edge shrink-0">
        <i cdkDragHandle
           class="pi pi-bars text-fg-faint text-xs cursor-grab"
           [attr.aria-label]="'Drag to reorder'"></i>
        <i [class]="kindIcon() + ' text-fg-muted text-xs'"></i>

        @if (editingTitle()) {
          <input
            pInputText
            type="text"
            class="text-xs flex-1 min-w-0"
            [(ngModel)]="draftTitle"
            (blur)="commitTitle()"
            (keydown.enter)="commitTitle()"
            (keydown.escape)="cancelTitleEdit()"
            #titleInput
          />
        } @else {
          <button
            type="button"
            class="text-xs font-medium text-fg flex-1 min-w-0 text-left truncate cursor-text bg-transparent border-0 p-0"
            (click)="startTitleEdit()"
          >
            {{ title() || kindLabel() }}
          </button>
        }

        <p-menu #menu [model]="menuItems()" [popup]="true" appendTo="body" />
        <p-button
          icon="pi pi-ellipsis-h"
          severity="secondary"
          [text]="true"
          [rounded]="true"
          size="small"
          (onClick)="menu.toggle($event)"
        />
        <p-button
          icon="pi pi-times"
          severity="secondary"
          [text]="true"
          [rounded]="true"
          size="small"
          pTooltip="Remove cell"
          (onClick)="delete.emit()"
        />
      </header>

      <div class="flex-1 min-h-0 flex flex-col">
        <ng-content />
      </div>

      <ng-content select="[cell-footer]" />
    </div>
  `,
})
export class AppDataCellShellComponent {
  kind = input.required<CellKind>();
  title = input<string | undefined>(undefined);

  rename = output<string>();
  delete = output<void>();
  duplicate = output<void>();
  moveUp = output<void>();
  moveDown = output<void>();

  editingTitle = signal(false);
  draftTitle = '';

  kindIcon = computed(() => KIND_ICONS[this.kind()]);
  kindLabel = computed(() => KIND_LABELS[this.kind()]);

  menuItems = computed<MenuItem[]>(() => [
    { label: 'Rename', icon: 'pi pi-pencil', command: () => this.startTitleEdit() },
    { label: 'Duplicate', icon: 'pi pi-copy', command: () => this.duplicate.emit() },
    { separator: true },
    { label: 'Move up', icon: 'pi pi-arrow-up', command: () => this.moveUp.emit() },
    { label: 'Move down', icon: 'pi pi-arrow-down', command: () => this.moveDown.emit() },
  ]);

  startTitleEdit(): void {
    this.draftTitle = this.title() ?? '';
    this.editingTitle.set(true);
  }

  commitTitle(): void {
    if (!this.editingTitle()) return;
    const next = this.draftTitle.trim();
    this.rename.emit(next);
    this.editingTitle.set(false);
  }

  cancelTitleEdit(): void {
    this.editingTitle.set(false);
  }
}
