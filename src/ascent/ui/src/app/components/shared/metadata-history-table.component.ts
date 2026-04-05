import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MetadataFieldInfo,
  MetadataSnapshotRow,
  BulkHistoryUpdate,
  BulkHistoryUpdateEntry,
  BulkHistoryInsertEntry,
  BulkHistoryDeleteEntry,
} from '../../models/asset.model';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { DatePicker } from 'primeng/datepicker';
import { Tag } from 'primeng/tag';
import { Checkbox } from 'primeng/checkbox';
import { Select } from 'primeng/select';

interface EditableRow {
  originalTimestamp: string;
  timestamp: Date;
  values: Record<string, string>;
  isNew: boolean;
  isDeleted: boolean;
  modifiedCells: Set<string>;
  timestampModified: boolean;
}

@Component({
  selector: 'app-metadata-history-table',
  standalone: true,
  imports: [FormsModule, TableModule, Card, Button, InputText, DatePicker, Tag, Checkbox, Select],
  template: `
    <p-card>
      <!-- Toolbar -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <p-button label="+ Insert Row" severity="primary" [outlined]="true" size="small" (onClick)="addRow()"/>
          @if (changeCount() > 0) {
            <p-tag [value]="changeCount() + ' pending change' + (changeCount() > 1 ? 's' : '')" severity="warn"/>
          }
        </div>
        <div class="flex items-center gap-2">
          @if (changeCount() > 0) {
            <p-button label="Save Changes" severity="primary" size="small" (onClick)="emitSave()"/>
            <p-button label="Discard" severity="secondary" [text]="true" size="small" (onClick)="discard()"/>
          }
        </div>
      </div>

      <!-- Table -->
      <p-table [value]="rows()" [scrollable]="true" scrollDirection="both" scrollHeight="32rem">
        <ng-template #header>
          <tr>
            <th class="w-52">Timestamp</th>
            @for (f of fields(); track f.metadata_id) {
              <th class="min-w-36">{{ f.metadata_display_name }}</th>
            }
            <th class="w-16"></th>
          </tr>
        </ng-template>
        <ng-template #body let-row let-i="rowIndex">
          <tr [class.opacity-40]="row.isDeleted" [class.line-through]="row.isDeleted">
            <!-- Timestamp cell -->
            <td class="py-3" [class.bg-blue-500/10]="row.timestampModified || row.isNew">
              <p-datepicker [(ngModel)]="row.timestamp" [showTime]="true" dateFormat="yy-mm-dd" hourFormat="24"
                            [style]="{'width': '100%'}" [disabled]="row.isDeleted"
                            [appendTo]="'body'"
                            (ngModelChange)="onTimestampChange(i)"/>
            </td>
            <!-- Value cells -->
            @for (f of fields(); track f.metadata_id) {
              <td class="py-3" [class.bg-blue-500/10]="row.modifiedCells.has(f.metadata_id)">
                @switch (f.value_type) {
                  @case ('boolean') {
                    <p-select [(ngModel)]="row.values[f.metadata_id]"
                              [options]="boolOptions" optionLabel="label" optionValue="value"
                              [disabled]="row.isDeleted" [appendTo]="'body'" styleClass="w-full text-xs"
                              (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('integer') {
                    <input type="number" pInputText [(ngModel)]="row.values[f.metadata_id]"
                           class="w-full font-mono text-xs" step="1" [disabled]="row.isDeleted"
                           (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('float') {
                    <input type="number" pInputText [(ngModel)]="row.values[f.metadata_id]"
                           class="w-full font-mono text-xs" step="any" [disabled]="row.isDeleted"
                           (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('date') {
                    <p-datepicker [(ngModel)]="row.values[f.metadata_id]"
                                  dateFormat="yy-mm-dd" [disabled]="row.isDeleted"
                                  [appendTo]="'body'" [style]="{'width': '100%'}"
                                  (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('time') {
                    <input type="time" pInputText [(ngModel)]="row.values[f.metadata_id]"
                           class="w-full font-mono text-xs" step="1" [disabled]="row.isDeleted"
                           (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('datetime') {
                    <p-datepicker [(ngModel)]="row.values[f.metadata_id]"
                                  [showTime]="true" dateFormat="yy-mm-dd" hourFormat="24"
                                  [disabled]="row.isDeleted" [appendTo]="'body'" [style]="{'width': '100%'}"
                                  (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('enum') {
                    <p-select [(ngModel)]="row.values[f.metadata_id]"
                              [options]="getEnumOptions(f)"
                              [disabled]="row.isDeleted" [appendTo]="'body'" styleClass="w-full text-xs"
                              (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @case ('reference') {
                    <p-select [(ngModel)]="row.values[f.metadata_id]"
                              [options]="referenceOptions()[f.metadata_id] || []"
                              optionLabel="label" optionValue="value"
                              [disabled]="row.isDeleted" [appendTo]="'body'" styleClass="w-full text-xs"
                              [filter]="true" filterPlaceholder="Search..."
                              (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                  @default {
                    <input type="text" pInputText [(ngModel)]="row.values[f.metadata_id]"
                           class="w-full font-mono text-xs" [disabled]="row.isDeleted"
                           (ngModelChange)="onCellChange(i, f.metadata_id)"/>
                  }
                }
              </td>
            }
            <!-- Actions -->
            <td class="py-3">
              @if (row.isDeleted) {
                <p-button icon="pi pi-undo" severity="secondary" [text]="true" size="small" (onClick)="undeleteRow(i)"/>
              } @else {
                <p-button icon="pi pi-trash" severity="danger" [text]="true" size="small" (onClick)="deleteRow(i)"/>
              }
            </td>
          </tr>
        </ng-template>
        <ng-template #emptymessage>
          <tr>
            <td [attr.colspan]="fields().length + 2" class="text-center text-surface-400 text-xs py-6">
              No history entries. Click + Insert Row to add one.
            </td>
          </tr>
        </ng-template>
      </p-table>
    </p-card>
  `,
})
export class MetadataHistoryTableComponent {
  fields = input.required<MetadataFieldInfo[]>();
  snapshots = input.required<MetadataSnapshotRow[]>();
  referenceOptions = input<Record<string, { label: string; value: string }[]>>({});
  save = output<BulkHistoryUpdate>();

  readonly boolOptions = [{ label: 'true', value: 'true' }, { label: 'false', value: 'false' }];

  rows = signal<EditableRow[]>([]);
  private initialized = false;

  ngOnChanges(): void {
    // Rebuild rows when inputs change (but not if user has pending edits)
    if (!this.initialized || this.changeCount() === 0) {
      this.buildRows();
      this.initialized = true;
    }
  }

  private buildRows(): void {
    const rows: EditableRow[] = this.snapshots().map(s => ({
      originalTimestamp: s.timestamp,
      timestamp: new Date(s.timestamp),
      values: this.snapshotToStrings(s.values),
      isNew: false,
      isDeleted: false,
      modifiedCells: new Set<string>(),
      timestampModified: false,
    }));
    this.rows.set(rows);
  }

  private snapshotToStrings(values: Record<string, any>): Record<string, string> {
    const result: Record<string, string> = {};
    for (const [key, val] of Object.entries(values)) {
      if (val === null || val === undefined) {
        result[key] = '';
      } else if (typeof val === 'object') {
        result[key] = JSON.stringify(val);
      } else {
        result[key] = String(val);
      }
    }
    return result;
  }

  onCellChange(rowIndex: number, metadataId: string): void {
    const row = this.rows()[rowIndex];
    if (!row || row.isNew) return;

    // Check if value differs from original
    const original = this.snapshots()[rowIndex];
    if (!original) return;
    const originalVal = original.values[metadataId];
    const originalStr = originalVal === null || originalVal === undefined
      ? '' : (typeof originalVal === 'object' ? JSON.stringify(originalVal) : String(originalVal));
    const currentStr = row.values[metadataId] ?? '';

    if (currentStr !== originalStr) {
      row.modifiedCells.add(metadataId);
    } else {
      row.modifiedCells.delete(metadataId);
    }
    this.rows.update(r => [...r]);
  }

  onTimestampChange(rowIndex: number): void {
    const row = this.rows()[rowIndex];
    if (!row || row.isNew) return;
    row.timestampModified = true;
    this.rows.update(r => [...r]);
  }

  addRow(): void {
    const newRow: EditableRow = {
      originalTimestamp: '',
      timestamp: new Date(),
      values: {},
      isNew: true,
      isDeleted: false,
      modifiedCells: new Set<string>(),
      timestampModified: false,
    };
    // Initialize empty values for all fields
    for (const f of this.fields()) {
      newRow.values[f.metadata_id] = '';
    }
    this.rows.update(r => [newRow, ...r]);
  }

  deleteRow(index: number): void {
    const row = this.rows()[index];
    if (row.isNew) {
      // Just remove new rows
      this.rows.update(r => r.filter((_, i) => i !== index));
    } else {
      row.isDeleted = true;
      this.rows.update(r => [...r]);
    }
  }

  undeleteRow(index: number): void {
    const row = this.rows()[index];
    row.isDeleted = false;
    this.rows.update(r => [...r]);
  }

  changeCount(): number {
    let count = 0;
    for (const row of this.rows()) {
      if (row.isNew) count++;
      else if (row.isDeleted) count++;
      else if (row.timestampModified) count++;
      else if (row.modifiedCells.size > 0) count += row.modifiedCells.size;
    }
    return count;
  }

  emitSave(): void {
    const updates: BulkHistoryUpdateEntry[] = [];
    const inserts: BulkHistoryInsertEntry[] = [];
    const deletes: BulkHistoryDeleteEntry[] = [];

    for (const row of this.rows()) {
      if (row.isDeleted && !row.isNew) {
        // Delete all entries at this timestamp
        deletes.push({ timestamp: row.originalTimestamp, metadata_id: null });
        continue;
      }

      if (row.isNew) {
        // Insert entries for all non-empty values
        for (const f of this.fields()) {
          const val = row.values[f.metadata_id];
          if (val !== '') {
            inserts.push({
              timestamp: row.timestamp.toISOString(),
              metadata_id: f.metadata_id,
              value: this.parseValue(val, f.value_type),
            });
          }
        }
        continue;
      }

      // Updates: modified cells or timestamp changes
      if (row.timestampModified || row.modifiedCells.size > 0) {
        const newTs = row.timestampModified ? row.timestamp.toISOString() : null;
        // For each field that has a value (modified or not, if timestamp changed)
        const fieldsToUpdate = row.timestampModified
          ? this.fields().map(f => f.metadata_id)
          : [...row.modifiedCells];

        for (const metadataId of fieldsToUpdate) {
          const field = this.fields().find(f => f.metadata_id === metadataId);
          if (!field) continue;
          const val = row.values[metadataId];
          if (val === '' && !row.modifiedCells.has(metadataId)) continue;

          // Check if this field existed in the original snapshot
          const originalSnapshot = this.snapshots().find(s => s.timestamp === row.originalTimestamp);
          const hadValue = originalSnapshot && metadataId in originalSnapshot.values;

          if (hadValue) {
            updates.push({
              old_timestamp: row.originalTimestamp,
              new_timestamp: newTs,
              metadata_id: metadataId,
              value: this.parseValue(val, field.value_type),
            });
          } else if (val !== '') {
            inserts.push({
              timestamp: (newTs ?? row.originalTimestamp),
              metadata_id: metadataId,
              value: this.parseValue(val, field.value_type),
            });
          }
        }
      }
    }

    this.save.emit({ updates, inserts, deletes });
  }

  /** Get enum options from a field's config. */
  getEnumOptions(field: MetadataFieldInfo): string[] {
    return (field.config?.['options'] as string[]) ?? [];
  }

  private parseValue(raw: string, valueType: string): any {
    if (valueType === 'integer') {
      const n = parseInt(raw, 10);
      return isNaN(n) ? raw : n;
    }
    if (valueType === 'float') {
      const n = parseFloat(raw);
      return isNaN(n) ? raw : n;
    }
    if (valueType === 'boolean') {
      return raw === 'true';
    }
    // enum and reference: string pass-through
    return raw;
  }

  discard(): void {
    this.buildRows();
  }
}
