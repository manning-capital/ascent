import { Component, input, output, signal } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Dialog } from 'primeng/dialog';
import { Button } from 'primeng/button';

/**
 * Modal dialog wrapper for create/edit forms. Caller owns the FormGroup
 * and the inner field markup; this component supplies the dialog frame,
 * header, footer (Save / Cancel), and validity-driven Save state.
 *
 *   <app-entity-edit-dialog
 *     [(visible)]="showAddField"
 *     title="Add Field"
 *     [form]="fieldForm"
 *     (save)="onSaveField()"
 *     (cancel)="onCancelField()">
 *     <app-form-field label="Name" [control]="fieldForm.controls.name" required>
 *       <input pInputText [formControl]="fieldForm.controls.name" />
 *     </app-form-field>
 *   </app-entity-edit-dialog>
 */
@Component({
  selector: 'app-entity-edit-dialog',
  standalone: true,
  imports: [Dialog, Button],
  template: `
    <p-dialog
      [(visible)]="visibleState"
      [header]="title()"
      [modal]="true"
      [draggable]="false"
      [resizable]="false"
      [closable]="!saving()"
      [closeOnEscape]="!saving()"
      [style]="{ width: width() }"
      (onHide)="onClosed()"
    >
      <ng-content />
      <ng-template pTemplate="footer">
        <p-button
          [label]="cancelLabel()"
          severity="secondary"
          [text]="true"
          size="small"
          [disabled]="saving()"
          (onClick)="onCancel()" />
        <p-button
          [label]="saveLabel()"
          severity="primary"
          size="small"
          icon="pi pi-check"
          [loading]="saving()"
          [disabled]="!canSave()"
          (onClick)="onSave()" />
      </ng-template>
    </p-dialog>
  `,
})
export class AppEntityEditDialogComponent {
  visible = input<boolean>(false);
  title = input.required<string>();
  form = input<FormGroup | null>(null);
  saving = input(false);
  saveLabel = input('Save');
  cancelLabel = input('Cancel');
  width = input<string>('32rem');

  readonly visibleChange = output<boolean>();
  readonly save = output<void>();
  readonly cancel = output<void>();

  visibleState = signal(false);

  constructor() {
    queueMicrotask(() => this.visibleState.set(this.visible()));
  }

  ngOnChanges(): void {
    this.visibleState.set(this.visible());
  }

  canSave(): boolean {
    if (this.saving()) return false;
    const f = this.form();
    if (!f) return true;
    return f.valid;
  }

  onSave(): void {
    const f = this.form();
    if (f && f.invalid) {
      f.markAllAsTouched();
      return;
    }
    this.save.emit();
  }

  onCancel(): void {
    this.visibleChange.emit(false);
    this.cancel.emit();
  }

  onClosed(): void {
    if (this.visible()) {
      this.visibleChange.emit(false);
    }
  }
}
