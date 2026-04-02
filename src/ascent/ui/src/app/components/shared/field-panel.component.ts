import { Component, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Panel } from 'primeng/panel';
import { Tag } from 'primeng/tag';
import { InputText } from 'primeng/inputtext';
import { Checkbox } from 'primeng/checkbox';
import { Select } from 'primeng/select';

export type PanelField = {
  label: string;
  key: string;
  required?: boolean;
  inherited?: boolean;
  subtitle?: string;
} & (
  | { type: 'text'; value: string | number | null; fallback?: string }
  | { type: 'mono'; value: string | null; fallback?: string }
  | { type: 'link'; value: string | null; route: string[]; fallback?: string; options?: { label: string; value: any }[] }
  | { type: 'external-link'; value: string | null; href: string | null; fallback?: string }
  | { type: 'active'; value: boolean }
  | { type: 'date'; value: string | null }
  | { type: 'tag'; value: string; severity?: string; options?: { label: string; value: any }[] }
  | { type: 'boolean'; value: boolean | null; fallback?: string }
  | { type: 'number'; value: number | null; step?: number; fallback?: string }
  | { type: 'time'; value: string | null; fallback?: string }
  | { type: 'datetime'; value: string | null; fallback?: string }
);

const BOOL_OPTIONS = [{ label: 'true', value: 'true' }, { label: 'false', value: 'false' }];

@Component({
  selector: 'app-field-panel',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, Panel, Tag, InputText, Checkbox, Select],
  host: { class: 'block' },
  template: `
    <p-panel [header]="header()">
      <div class="flex flex-wrap gap-x-6 gap-y-4">
        @for (field of fields(); track field.key) {
          <div class="min-w-0 flex-1 basis-[calc(25%-1.125rem)]">
            <label class="block text-xs text-surface-500 mb-1">
              {{ field.label }}
              @if (field.required) { <span class="text-red-500">*</span> }
              @if (field.inherited) { <span class="text-surface-400 italic text-[0.6875rem] ml-1">(inherited)</span> }
            </label>
            @if (editing() && isEditable(field)) {
              @switch (field.type) {
                @case ('text') {
                  <input pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" class="w-full text-sm"/>
                }
                @case ('mono') {
                  <input pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" class="w-full text-sm font-mono"/>
                }
                @case ('link') {
                  <p-select [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" [options]="$any(field).options || []" optionLabel="label" optionValue="value" class="w-full" [filter]="true" placeholder="Select..."/>
                }
                @case ('external-link') {
                  <input pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" class="w-full text-sm"/>
                }
                @case ('active') {
                  <div class="flex items-center h-[2.375rem]">
                    <p-checkbox [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" [binary]="true"/>
                    <span class="text-sm text-surface-500 ml-2">{{ ev(field.key) ? 'Yes' : 'No' }}</span>
                  </div>
                }
                @case ('tag') {
                  <p-select [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" [options]="$any(field).options || []" class="w-full"/>
                }
                @case ('boolean') {
                  <p-select [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" [options]="boolOptions" class="w-full"/>
                }
                @case ('number') {
                  <input type="number" pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" [step]="$any(field).step ?? 1" class="w-full text-sm"/>
                }
                @case ('time') {
                  <input type="time" pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" step="1" class="w-full text-sm"/>
                }
                @case ('datetime') {
                  <input type="datetime-local" pInputText [ngModel]="ev(field.key)" (ngModelChange)="onEdit(field.key, $event)" step="1" class="w-full text-sm"/>
                }
              }
            } @else {
              @switch (field.type) {
                @case ('text') {
                  <div class="text-sm py-1.5">{{ field.value ?? $any(field).fallback ?? '-' }}</div>
                }
                @case ('mono') {
                  <div class="text-sm font-mono py-1.5">{{ field.value ?? $any(field).fallback ?? '-' }}</div>
                }
                @case ('link') {
                  <div class="text-sm py-1.5">
                    @if (field.value && $any(field).route?.length) {
                      <a [routerLink]="$any(field).route" class="text-primary hover:underline">{{ field.value }}</a>
                    } @else {
                      {{ $any(field).fallback ?? '-' }}
                    }
                  </div>
                }
                @case ('external-link') {
                  <div class="text-sm py-1.5">
                    @if (field.value && $any(field).href) {
                      <a [href]="$any(field).href" target="_blank" class="text-primary hover:underline truncate block">{{ field.value }}</a>
                    } @else {
                      {{ $any(field).fallback ?? '-' }}
                    }
                  </div>
                }
                @case ('active') {
                  <div class="text-sm py-1.5">
                    <span class="inline-flex items-center gap-1.5">
                      <span class="w-2 h-2 rounded-full" [class]="field.value ? 'bg-green-500' : 'bg-surface-400'"></span>
                      {{ field.value ? 'Yes' : 'No' }}
                    </span>
                  </div>
                }
                @case ('date') {
                  @if (field.value) {
                    <div class="text-sm py-1.5">{{ field.value | date:'mediumDate' }}</div>
                  }
                }
                @case ('tag') {
                  <div class="py-1.5"><p-tag [value]="field.value" [severity]="$any(field).severity ?? 'secondary'"/></div>
                }
                @case ('boolean') {
                  <div class="text-sm font-mono py-1.5">{{ field.value != null ? field.value : ($any(field).fallback ?? 'Not set') }}</div>
                }
                @case ('number') {
                  <div class="text-sm font-mono py-1.5">{{ field.value != null ? field.value : ($any(field).fallback ?? 'Not set') }}</div>
                }
                @case ('time') {
                  <div class="text-sm py-1.5">{{ field.value ?? ($any(field).fallback ?? '-') }}</div>
                }
                @case ('datetime') {
                  <div class="text-sm py-1.5">{{ field.value ?? ($any(field).fallback ?? '-') }}</div>
                }
              }
              @if (field.subtitle) {
                <div class="text-[0.6875rem] text-surface-400 -mt-0.5">{{ field.subtitle }}</div>
              }
            }
          </div>
        }
      </div>
    </p-panel>
  `,
})
export class FieldPanelComponent {
  header = input.required<string>();
  fields = input.required<PanelField[]>();
  editing = input(false);
  editValues = input<Record<string, any>>({});
  editChange = output<{ key: string; value: any }>();

  readonly boolOptions = BOOL_OPTIONS;

  ev(key: string): any {
    return this.editValues()[key];
  }

  onEdit(key: string, value: any): void {
    this.editChange.emit({ key, value });
  }

  isEditable(field: PanelField): boolean {
    if (field.type === 'date') return false;
    return field.key in this.editValues();
  }
}
