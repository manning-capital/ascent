import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Dialog } from 'primeng/dialog';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Skeleton } from 'primeng/skeleton';
import { EntityUsage } from '../../models/field.model';

@Component({
  selector: 'app-safe-delete-dialog',
  standalone: true,
  imports: [FormsModule, Dialog, Button, InputText, Message, Skeleton],
  template: `
    <p-dialog [header]="'Delete ' + entityLabel" [(visible)]="visible" (visibleChange)="visibleChange.emit($event); onVisibilityChange($event)" [modal]="true" [style]="{width: '36rem'}" [closable]="true" [draggable]="false">
      <div class="flex flex-col gap-4">
        <p-message severity="error">
          This action is permanent and cannot be undone. All data associated with this {{ entityLabel.toLowerCase() }} will be deleted.
        </p-message>

        @if (usage) {
          @if (cascadeItems.length > 0) {
            <div>
              <p class="text-sm font-semibold mb-2">Data that will be permanently deleted:</p>
              <div class="flex flex-col gap-1 text-sm">
                @for (item of cascadeItems; track item.label) {
                  <div class="flex justify-between px-3 py-1.5 rounded bg-negative/5 border border-negative/10">
                    <span class="text-surface-400">{{ item.label }}</span>
                    <span class="font-mono text-negative">{{ item.count }} {{ item.count === 1 ? 'record' : 'records' }}</span>
                  </div>
                }
              </div>
            </div>
          }

          @if (referenceItems.length > 0) {
            <div>
              <p class="text-sm font-semibold mb-2">References that will break:</p>
              <div class="flex flex-col gap-1 text-sm">
                @for (item of referenceItems; track item.label) {
                  <div class="flex justify-between px-3 py-1.5 rounded bg-warning/5 border border-warning/10">
                    <span class="text-surface-400">{{ item.label }}</span>
                    <span class="font-mono text-warning">{{ item.count }} {{ item.count === 1 ? 'reference' : 'references' }}</span>
                  </div>
                }
              </div>
            </div>
          }

          @if (usage.total > 0) {
            <div class="flex justify-between px-3 py-1.5 rounded bg-emphasis font-semibold border border-surface text-sm">
              <span>Total affected</span>
              <span class="font-mono">{{ usage.total }}</span>
            </div>
          } @else {
            <p class="text-sm text-surface-400">No data is currently using this {{ entityLabel.toLowerCase() }}.</p>
          }

          <div>
            <label class="block text-sm mb-2">Type <span class="font-mono font-semibold">{{ entityName }}</span> to confirm:</label>
            <input type="text" pInputText [(ngModel)]="confirmName" placeholder="Type the name to confirm" class="w-full"/>
          </div>

          <div class="flex justify-end gap-2">
            <p-button (onClick)="close()" severity="secondary" [outlined]="true" size="small" label="Cancel"/>
            <p-button (onClick)="onConfirm()" severity="danger" size="small" label="Delete Permanently" [disabled]="!canDelete" [loading]="deleting"/>
          </div>
        } @else {
          <div class="flex flex-col gap-2">
            <p-skeleton width="100%" height="1.5rem"/>
            <p-skeleton width="80%" height="1.5rem"/>
            <p-skeleton width="60%" height="1.5rem"/>
          </div>
        }
      </div>
    </p-dialog>
  `,
})
export class SafeDeleteDialogComponent {
  @Input() visible = false;
  @Input() entityLabel = '';
  @Input() entityName = '';
  @Input() usage: EntityUsage | null = null;
  @Input() deleting = false;

  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() confirm = new EventEmitter<void>();

  confirmName = '';

  get cascadeItems() {
    return this.usage?.items.filter(i => i.kind === 'cascade' && i.count > 0) ?? [];
  }

  get referenceItems() {
    return this.usage?.items.filter(i => i.kind === 'reference' && i.count > 0) ?? [];
  }

  get canDelete(): boolean {
    return this.confirmName === this.entityName && !this.deleting && !!this.usage;
  }

  onVisibilityChange(visible: boolean): void {
    if (!visible) this.confirmName = '';
  }

  close(): void {
    this.confirmName = '';
    this.visible = false;
    this.visibleChange.emit(false);
  }

  onConfirm(): void {
    if (this.canDelete) {
      this.confirm.emit();
    }
  }
}
