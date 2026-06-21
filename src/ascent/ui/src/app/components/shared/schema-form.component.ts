import { Component, computed, effect, inject, input, output, untracked } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Select } from 'primeng/select';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { InputNumber } from 'primeng/inputnumber';
import { InputText } from 'primeng/inputtext';
import { AppFormFieldComponent } from '../ui/form-field/app-form-field.component';
import { JsonSchema, JsonSchemaProperty } from '../../models/strategy.model';

interface FormField {
  key: string;
  label: string;
  description: string;
  type: 'string' | 'number' | 'boolean' | 'select';
  options?: string[];
  min?: number;
  max?: number;
  required: boolean;
  nullable: boolean;
}

/**
 * Renders a JSON-Schema-driven form using Reactive Forms internally.
 *
 * Backward-compatible contract: callers pass ``[schema]`` + ``[data]`` and
 * receive ``(valuesChange)`` events — the same API as before. Internally
 * we now construct a ``FormGroup`` from the schema (with ``Validators`` for
 * ``required`` / ``min`` / ``max``) and wrap each control in
 * ``AppFormField`` so labels, the required asterisk, and inline validation
 * errors all come through the shared primitive.
 *
 * Callers that want full reactive-forms ownership can supply their own
 * ``[formGroup]`` instead; in that case we render it directly and don't
 * rebuild from the schema.
 */
@Component({
  selector: 'app-schema-form',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    AppFormFieldComponent,
    Select,
    ToggleSwitch,
    InputNumber,
    InputText,
  ],
  template: `
    <form [formGroup]="form()" class="space-y-4">
      @for (field of fields(); track field.key) {
        <app-form-field
          [label]="field.label"
          [required]="field.required"
          [hint]="field.description || undefined"
          [control]="form().get(field.key)"
          [for]="'sf-' + field.key"
        >
          @switch (field.type) {
            @case ('select') {
              <p-select
                [inputId]="'sf-' + field.key"
                [options]="field.options ?? []"
                [formControlName]="field.key"
                placeholder="Select…"
                appendTo="body"
                size="small"
              />
            }
            @case ('boolean') {
              <p-toggleswitch
                [inputId]="'sf-' + field.key"
                [formControlName]="field.key"
              />
            }
            @case ('number') {
              <p-inputNumber
                [inputId]="'sf-' + field.key"
                [formControlName]="field.key"
                [min]="field.min"
                [max]="field.max"
                [minFractionDigits]="0"
                [maxFractionDigits]="10"
                mode="decimal"
                size="small"
              />
            }
            @default {
              <input
                [id]="'sf-' + field.key"
                type="text"
                pInputText
                class="w-full"
                [formControlName]="field.key"
                [readOnly]="readonly()"
              />
            }
          }
        </app-form-field>
      }

      @if (fields().length === 0) {
        <p class="text-sm text-fg-faint italic">No parameters defined.</p>
      }
    </form>
  `,
})
export class SchemaFormComponent {
  schema = input<JsonSchema | null>(null);
  data = input<Record<string, any>>({});
  readonly = input<boolean>(true);
  /** Optional caller-owned FormGroup. When supplied, ``schema`` / ``data``
   *  are still consulted for layout (labels, types) but the controls bound
   *  to inputs are read from this group. */
  formGroup = input<FormGroup | null>(null);

  valuesChange = output<Record<string, any>>();
  /** Emits whenever the form's validity flips — useful for parent Save
   *  buttons that want to disable while invalid. */
  validChange = output<boolean>();

  private fb = inject(FormBuilder);
  private internalForm = new FormGroup({});

  fields = computed<FormField[]>(() => {
    const s = this.schema();
    if (!s?.properties) return [];
    return this.buildFields(s);
  });

  /** Effective form group — caller-supplied or our internal one. */
  form = computed<FormGroup>(() => this.formGroup() ?? this.internalForm);

  constructor() {
    // (Re)build the internal form when schema / data changes — only when no
    // external FormGroup is provided. Skip-otherwise so caller-supplied groups
    // aren't clobbered.
    effect(() => {
      if (this.formGroup()) return;
      const flds = this.fields();
      const data = this.data();
      untracked(() => this.rebuildInternalForm(flds, data));
    });

    // Toggle readonly via enable/disable on the effective form.
    effect(() => {
      const ro = this.readonly();
      const form = this.form();
      untracked(() => {
        if (ro) form.disable({ emitEvent: false });
        else form.enable({ emitEvent: false });
      });
    });

    // Stream changes to the parent — mirrors the legacy data + valuesChange
    // contract so existing callers (strategy-detail, feed-detail) keep
    // working without changes.
    effect(() => {
      const form = this.form();
      const sub = form.valueChanges.subscribe((v) => {
        this.valuesChange.emit({ ...v });
      });
      const validSub = form.statusChanges.subscribe(() => {
        this.validChange.emit(form.valid);
      });
      return () => {
        sub.unsubscribe();
        validSub.unsubscribe();
      };
    });
  }

  private rebuildInternalForm(fields: FormField[], data: Record<string, any>): void {
    // Drop existing controls
    for (const key of Object.keys(this.internalForm.controls)) {
      this.internalForm.removeControl(key, { emitEvent: false });
    }
    // Add controls per field with validators derived from the schema
    for (const field of fields) {
      const validators = [];
      if (field.required) validators.push(Validators.required);
      if (field.min != null) validators.push(Validators.min(field.min));
      if (field.max != null) validators.push(Validators.max(field.max));
      this.internalForm.addControl(
        field.key,
        new FormControl(data?.[field.key] ?? null, validators),
        { emitEvent: false },
      );
    }
  }

  /** Public helper for callers who want to read the form state directly. */
  getControl(key: string): AbstractControl | null {
    return this.form().get(key);
  }

  // ─── Schema → field model (unchanged) ─────────────────────
  private buildFields(schema: JsonSchema): FormField[] {
    const props = schema.properties || {};
    const required = new Set(schema.required || []);

    return Object.entries(props).map(([key, prop]) => {
      const resolved = this.resolveType(prop);
      return {
        key,
        label: prop.title || this.toLabel(key),
        description: prop.description || '',
        type: resolved.type,
        options: resolved.options,
        min: prop.minimum ?? prop.exclusiveMinimum,
        max: prop.maximum ?? prop.exclusiveMaximum,
        required: required.has(key),
        nullable: resolved.nullable,
      };
    });
  }

  private resolveType(prop: JsonSchemaProperty): {
    type: FormField['type'];
    options?: string[];
    nullable: boolean;
  } {
    if (prop.enum) {
      return { type: 'select', options: prop.enum, nullable: false };
    }
    if (prop.anyOf) {
      const nullable = prop.anyOf.some((a) => a.type === 'null');
      const nonNull = prop.anyOf.filter((a) => a.type !== 'null');
      if (nonNull.length === 1) {
        const inner = nonNull[0];
        if (inner.enum) {
          return { type: 'select', options: inner.enum, nullable };
        }
        return { type: this.mapJsonType(inner.type), nullable };
      }
    }
    return { type: this.mapJsonType(prop.type), nullable: false };
  }

  private mapJsonType(type?: string): FormField['type'] {
    switch (type) {
      case 'integer':
      case 'number':
        return 'number';
      case 'boolean':
        return 'boolean';
      default:
        return 'string';
    }
  }

  private toLabel(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
