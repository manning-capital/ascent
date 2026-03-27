import { Component, input, output, signal, effect, EventEmitter } from '@angular/core';
import { FormsModule } from '@angular/forms';
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

@Component({
  selector: 'app-schema-form',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="space-y-4" [class.opacity-50]="readonly()" [class.pointer-events-none]="readonly()">
      @for (field of fields(); track field.key) {
        <div>
          <label class="block text-xs font-medium text-fg-muted mb-1">
            {{ field.label }}
            @if (field.required) {
              <span class="text-negative">*</span>
            }
          </label>

          @if (field.type === 'select') {
            <select
              class="w-full rounded-lg border border-edge bg-elevated px-3 py-2 text-sm text-fg-muted cursor-not-allowed"
              [class]="readonly() ? '' : '!text-fg !cursor-auto focus:outline-none focus:ring-1 focus:ring-info'"
              [ngModel]="values()[field.key]"
              (ngModelChange)="onFieldChange(field.key, $event)"
              [disabled]="readonly()">
              @for (opt of field.options; track opt) {
                <option [value]="opt">{{ opt }}</option>
              }
            </select>
          } @else if (field.type === 'boolean') {
            <button
              type="button"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              [class]="(values()[field.key] ? 'bg-info' : 'bg-elevated') + (readonly() ? ' cursor-not-allowed' : ' focus:outline-none focus:ring-1 focus:ring-info')"
              [disabled]="readonly()"
              (click)="onFieldChange(field.key, !values()[field.key])">
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                [class]="values()[field.key] ? 'translate-x-6' : 'translate-x-1'">
              </span>
            </button>
          } @else if (field.type === 'number') {
            <input
              type="number"
              class="w-full rounded-lg border border-edge bg-elevated px-3 py-2 text-sm text-fg-muted cursor-not-allowed"
              [class]="readonly() ? '' : '!text-fg !cursor-auto focus:outline-none focus:ring-1 focus:ring-info'"
              [ngModel]="values()[field.key]"
              (ngModelChange)="onFieldChange(field.key, $event)"
              [attr.min]="field.min"
              [attr.max]="field.max"
              [attr.step]="field.type === 'number' ? 'any' : null"
              [readOnly]="readonly()"/>
          } @else {
            <input
              type="text"
              class="w-full rounded-lg border border-edge bg-elevated px-3 py-2 text-sm text-fg-muted cursor-not-allowed"
              [class]="readonly() ? '' : '!text-fg !cursor-auto focus:outline-none focus:ring-1 focus:ring-info'"
              [ngModel]="values()[field.key]"
              (ngModelChange)="onFieldChange(field.key, $event)"
              [readOnly]="readonly()"/>
          }

          @if (field.description) {
            <p class="text-xs text-fg-faint mt-1">{{ field.description }}</p>
          }
        </div>
      }

      @if (fields().length === 0) {
        <p class="text-sm text-fg-faint italic">No parameters defined.</p>
      }
    </div>
  `,
})
export class SchemaFormComponent {
  schema = input<JsonSchema | null>(null);
  data = input<Record<string, any>>({});
  readonly = input<boolean>(true);

  valuesChange = output<Record<string, any>>();

  fields = signal<FormField[]>([]);
  values = signal<Record<string, any>>({});

  constructor() {
    effect(() => {
      const s = this.schema();
      const d = this.data();
      if (s?.properties) {
        this.fields.set(this.buildFields(s));
      } else {
        this.fields.set([]);
      }
      this.values.set({ ...d });
    });
  }

  onFieldChange(key: string, value: any): void {
    const updated = { ...this.values(), [key]: value };
    this.values.set(updated);
    this.valuesChange.emit(updated);
  }

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
    // Pydantic Literal -> enum
    if (prop.enum) {
      return { type: 'select', options: prop.enum, nullable: false };
    }

    // Pydantic Optional/Union -> anyOf
    if (prop.anyOf) {
      const nullable = prop.anyOf.some((a: any) => a.type === 'null');
      const nonNull = prop.anyOf.filter((a: any) => a.type !== 'null');
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
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
