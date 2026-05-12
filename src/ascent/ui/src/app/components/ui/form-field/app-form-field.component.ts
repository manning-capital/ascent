import { Component, computed, input } from '@angular/core';
import { AbstractControl } from '@angular/forms';
import { Message } from 'primeng/message';

/**
 * Standard form-field wrapper: label + projected control + validation message.
 *
 *   <app-form-field label="Display Name" [control]="form.get('display_name')" required>
 *     <input pInputText [formControl]="$any(form.get('display_name'))" />
 *   </app-form-field>
 *
 * The `control` input is what we read for `dirty`, `touched`, and `errors`.
 * Pass-through projection lets callers use whatever PrimeNG control fits.
 */
@Component({
  selector: 'app-form-field',
  standalone: true,
  imports: [Message],
  template: `
    <div class="flex flex-col gap-1">
      @if (label()) {
        <label
          [for]="for()"
          class="text-[11px] font-medium text-fg-muted uppercase tracking-wider"
        >
          {{ label() }}
          @if (required()) {
            <span class="text-negative ml-0.5" aria-hidden="true">*</span>
          }
        </label>
      }
      <ng-content />
      @if (hint() && !showError()) {
        <p class="text-[11px] text-fg-faint">{{ hint() }}</p>
      }
      @if (showError()) {
        <p-message severity="error" size="small" [text]="errorMessage()" />
      }
    </div>
  `,
})
export class AppFormFieldComponent {
  label = input<string | undefined>(undefined);
  for = input<string | undefined>(undefined);
  required = input(false);
  hint = input<string | undefined>(undefined);
  control = input<AbstractControl | null | undefined>(undefined);
  errorMap = input<Record<string, string> | undefined>(undefined);

  showError = computed(() => {
    const c = this.control();
    if (!c || !c.errors) return false;
    return c.touched || c.dirty;
  });

  errorMessage = computed<string>(() => {
    const c = this.control();
    const errors = c?.errors;
    if (!errors) return '';
    const map = this.errorMap() ?? {};
    const key = Object.keys(errors)[0];
    if (map[key]) return map[key];
    switch (key) {
      case 'required': return 'Required.';
      case 'min': return `Minimum: ${errors['min']?.min ?? ''}.`;
      case 'max': return `Maximum: ${errors['max']?.max ?? ''}.`;
      case 'minlength': return `At least ${errors['minlength']?.requiredLength} characters.`;
      case 'maxlength': return `At most ${errors['maxlength']?.requiredLength} characters.`;
      case 'email': return 'Invalid email address.';
      case 'pattern': return 'Invalid format.';
      default: return 'Invalid value.';
    }
  });
}
