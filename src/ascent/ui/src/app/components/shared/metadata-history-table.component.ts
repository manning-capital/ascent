import { Component, computed, effect, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { InputNumber } from 'primeng/inputnumber';
import { InputText } from 'primeng/inputtext';
import { Table, TableModule } from 'primeng/table';
import {
  MetadataFieldInfo,
  MetadataSnapshotRow,
  BulkHistoryUpdate,
  BulkHistoryUpdateEntry,
  BulkHistoryInsertEntry,
  BulkHistoryDeleteEntry,
} from '../../models/asset.model';

/** Stable internal-row shape with change-tracking metadata. */
interface GridRow {
  __id: string;
  __originalTimestamp: string;
  __isNew: boolean;
  __isDeleted: boolean;
  __modifiedCells: Set<string>;
  __timestampModified: boolean;
  __originalValues: Record<string, string>;
  /** Local-time display string for the timestamp column. */
  timestamp: string;
  [key: string]: any;
}

function formatLocalDateTime(d: Date): string {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const mo = months[d.getMonth()];
  const day = d.getDate();
  const y = d.getFullYear();
  const h = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${mo} ${day}, ${y} ${h}:${mi}:${s}`;
}

function toDate(value: string): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Editable metadata-history grid built on PrimeNG ``p-table`` with cell-level
 * edit mode. Inputs: ``[fields] / [snapshots] / [loading] / [referenceOptions]``.
 * Output: ``(save)`` emits a ``BulkHistoryUpdate``.
 *
 * Each cell renders one of seven editors based on the field's ``value_type``
 * (boolean / integer / float / date / time / datetime / enum / reference /
 * text). Modified cells, modified timestamps, and new rows get tinted with
 * the primary color; deleted rows fade. Insert / Delete / Discard / Save
 * actions live in the toolbar above the table.
 */
@Component({
  selector: 'app-metadata-history-table',
  standalone: true,
  imports: [
    FormsModule,
    TableModule,
    Button,
    Tag,
    Select,
    DatePicker,
    InputNumber,
    InputText,
  ],
  host: { class: 'block' },
  styles: [`
    /* Tint background of cells that are pending changes (insert / modify). */
    :host ::ng-deep td.history-cell--modified {
      background: color-mix(in srgb, var(--p-primary-color) 12%, transparent);
    }
    :host ::ng-deep tr.history-row--deleted > td {
      opacity: 0.4;
      text-decoration: line-through;
    }
    /* Compact editors so they fit a single row height. */
    :host ::ng-deep td .p-select,
    :host ::ng-deep td .p-datepicker,
    :host ::ng-deep td .p-inputtext,
    :host ::ng-deep td .p-inputnumber {
      width: 100%;
    }
  `],
  template: `
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
    <div class="border border-edge rounded-md overflow-hidden">
      <p-table
        [value]="rowData()"
        [loading]="loading()"
        dataKey="__id"
        styleClass="text-xs"
      >
        <ng-template pTemplate="header">
          <tr>
            <th class="text-[11px] uppercase tracking-wider font-semibold text-fg-muted px-3 py-2" style="width: 220px;">
              Timestamp
            </th>
            @for (f of fields(); track f.metadata_id) {
              <th class="text-[11px] uppercase tracking-wider font-semibold text-fg-muted px-3 py-2" style="min-width: 140px;">
                {{ f.metadata_display_name }}
              </th>
            }
            <th class="px-2 py-2" style="width: 48px;"></th>
          </tr>
        </ng-template>

        <ng-template pTemplate="body" let-row let-rowIndex="rowIndex">
          <tr [class.history-row--deleted]="row.__isDeleted">
            <!-- Timestamp column — always-visible datetime picker. PrimeNG's
                 p-cellEditor + appendTo="body" overlay combo deadlocks (every
                 click inside the body-mounted calendar registers as "outside
                 the cell" and the editor tries to exit while the overlay is
                 still alive). Rendering each editor inline avoids that
                 click-outside dance entirely. -->
            <td
              [class.history-cell--modified]="row.__isNew || row.__timestampModified"
              class="px-3 py-2"
            >
              <p-datepicker
                [ngModel]="toDate(row.timestamp)"
                (ngModelChange)="onTimestampChange(row, $event)"
                [showTime]="true"
                [showSeconds]="true"
                [disabled]="row.__isDeleted"
                appendTo="body"
                dateFormat="M d, yy"
                size="small"
                styleClass="w-full"
              />
            </td>

            <!-- One cell per metadata field; editor chosen by value_type -->
            @for (f of fields(); track f.metadata_id) {
              <td
                [class.history-cell--modified]="row.__isNew || row.__modifiedCells.has(f.metadata_id)"
                class="px-3 py-2"
              >
                @switch (f.value_type) {
                  @case ('boolean') {
                    <p-select
                      [options]="booleanOptions"
                      optionLabel="label"
                      optionValue="value"
                      [ngModel]="row[f.metadata_id]"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      appendTo="body"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('integer') {
                    <p-inputNumber
                      [ngModel]="numberValue(row[f.metadata_id])"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      [showButtons]="false"
                      [step]="1"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('float') {
                    <p-inputNumber
                      [ngModel]="numberValue(row[f.metadata_id])"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      [showButtons]="false"
                      [minFractionDigits]="0"
                      [maxFractionDigits]="10"
                      mode="decimal"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('date') {
                    <p-datepicker
                      [ngModel]="toDate(row[f.metadata_id])"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      dateFormat="yy-mm-dd"
                      appendTo="body"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('datetime') {
                    <p-datepicker
                      [ngModel]="toDate(row[f.metadata_id])"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      [showTime]="true"
                      [showSeconds]="true"
                      dateFormat="M d, yy"
                      appendTo="body"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('enum') {
                    <p-select
                      [options]="enumOptionsFor(f)"
                      [ngModel]="row[f.metadata_id]"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      [filter]="true"
                      appendTo="body"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @case ('reference') {
                    <p-select
                      [options]="referenceOptionsFor(f)"
                      optionLabel="label"
                      optionValue="value"
                      [ngModel]="row[f.metadata_id]"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [disabled]="row.__isDeleted"
                      [filter]="true"
                      appendTo="body"
                      size="small"
                      styleClass="w-full"
                    />
                  }
                  @default {
                    <input
                      pInputText
                      type="text"
                      [ngModel]="row[f.metadata_id]"
                      (ngModelChange)="onCellChange(row, f, $event)"
                      [readOnly]="row.__isDeleted"
                      class="w-full text-xs"
                    />
                  }
                }
              </td>
            }

            <!-- Action column: delete / undo -->
            <td class="px-2 py-2 text-right">
              @if (row.__isDeleted) {
                <p-button
                  icon="pi pi-undo"
                  severity="secondary"
                  [text]="true"
                  [rounded]="true"
                  size="small"
                  pTooltip="Undo delete"
                  (onClick)="undeleteRow(row, $event)"
                />
              } @else {
                <p-button
                  icon="pi pi-trash"
                  severity="danger"
                  [text]="true"
                  [rounded]="true"
                  size="small"
                  pTooltip="Delete row"
                  (onClick)="deleteRow(row, $event)"
                />
              }
            </td>
          </tr>
        </ng-template>

        <ng-template pTemplate="emptymessage">
          <tr>
            <td [attr.colspan]="fields().length + 2" class="text-center text-xs text-fg-faint py-6">
              No history entries. Click + Insert Row to add one.
            </td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `,
})
export class MetadataHistoryTableComponent {
  // ─── Inputs / outputs ─────────────────────────────────
  fields = input.required<MetadataFieldInfo[]>();
  snapshots = input.required<MetadataSnapshotRow[]>();
  referenceOptions = input<Record<string, { label: string; value: string }[]>>({});
  loading = input(false);
  save = output<BulkHistoryUpdate>();

  // ─── State ────────────────────────────────────────────
  rowData = signal<GridRow[]>([]);
  changeCount = signal(0);
  private newRowCounter = 0;
  private initialized = false;

  booleanOptions: { label: string; value: string }[] = [
    { label: '—', value: '' },
    { label: 'True', value: 'true' },
    { label: 'False', value: 'false' },
  ];

  // Expose helpers to the template
  readonly toDate = toDate;
  readonly numberValue = (v: any): number | null => {
    if (v === '' || v == null) return null;
    const n = Number(v);
    return isNaN(n) ? null : n;
  };

  constructor() {
    // Rebuild rows when fields / snapshots change AND there are no pending
    // unsaved changes. (Preserve user edits across reactive parent updates.)
    effect(() => {
      this.fields();
      this.snapshots();
      untracked(() => {
        if (!this.initialized || this.changeCount() === 0) {
          this.rowData.set(this.buildRows());
          this.updateChangeCount();
          this.initialized = true;
        }
      });
    });
  }

  // ─── Event handlers ───────────────────────────────────
  onCellChange(row: GridRow, field: MetadataFieldInfo, value: any): void {
    const id = field.metadata_id;
    const current = this.formatForStorage(value, field.value_type);
    this.rowData.update((rows) =>
      rows.map((r) => {
        if (r.__id !== row.__id) return r;
        const next: GridRow = { ...r, [id]: current };
        if (next.__isNew) {
          // New rows are entirely "modified" — no need to track per-cell.
          return next;
        }
        const original = r.__originalValues[id] ?? '';
        const modified = new Set(r.__modifiedCells);
        if (current !== original) modified.add(id);
        else modified.delete(id);
        next.__modifiedCells = modified;
        return next;
      }),
    );
    this.updateChangeCount();
  }

  onTimestampChange(row: GridRow, value: Date | null): void {
    const newDisplay = value ? formatLocalDateTime(value) : '';
    this.rowData.update((rows) =>
      rows.map((r) => {
        if (r.__id !== row.__id) return r;
        const next: GridRow = { ...r, timestamp: newDisplay };
        next.__timestampModified = newDisplay !== r.__originalTimestamp;
        return next;
      }),
    );
    this.updateChangeCount();
  }

  // ─── Row operations ───────────────────────────────────
  addRow(): void {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const newRow: GridRow = {
      __id: `new-${this.newRowCounter++}`,
      __originalTimestamp: '',
      __isNew: true,
      __isDeleted: false,
      __modifiedCells: new Set<string>(),
      __timestampModified: false,
      __originalValues: {},
      timestamp: formatLocalDateTime(now),
    };
    for (const f of this.fields()) {
      newRow[f.metadata_id] = '';
    }
    this.rowData.update((rows) => [newRow, ...rows]);
    this.updateChangeCount();
  }

  deleteRow(row: GridRow, event: Event): void {
    event.stopPropagation();
    if (row.__isNew) {
      this.rowData.update((rows) => rows.filter((r) => r.__id !== row.__id));
    } else {
      this.rowData.update((rows) =>
        rows.map((r) => (r.__id === row.__id ? { ...r, __isDeleted: true } : r)),
      );
    }
    this.updateChangeCount();
  }

  undeleteRow(row: GridRow, event: Event): void {
    event.stopPropagation();
    this.rowData.update((rows) =>
      rows.map((r) => (r.__id === row.__id ? { ...r, __isDeleted: false } : r)),
    );
    this.updateChangeCount();
  }

  discard(): void {
    this.newRowCounter = 0;
    this.rowData.set(this.buildRows());
    this.updateChangeCount();
  }

  // ─── Save (same shape as previous emit) ───────────────
  emitSave(): void {
    const updates: BulkHistoryUpdateEntry[] = [];
    const inserts: BulkHistoryInsertEntry[] = [];
    const deletes: BulkHistoryDeleteEntry[] = [];

    for (const row of this.rowData()) {
      if (row.__isDeleted && !row.__isNew) {
        deletes.push({ timestamp: row.__originalTimestamp, metadata_id: null });
        continue;
      }
      if (row.__isNew) {
        for (const f of this.fields()) {
          const val = row[f.metadata_id];
          if (val !== '' && val != null) {
            inserts.push({
              timestamp: row.timestamp,
              metadata_id: f.metadata_id,
              value: this.parseValue(val, f.value_type),
            });
          }
        }
        continue;
      }
      if (row.__timestampModified || row.__modifiedCells.size > 0) {
        const newTs = row.__timestampModified ? row.timestamp : null;
        const fieldsToUpdate = row.__timestampModified
          ? this.fields().map((f) => f.metadata_id)
          : [...row.__modifiedCells];

        for (const metadataId of fieldsToUpdate) {
          const field = this.fields().find((f) => f.metadata_id === metadataId);
          if (!field) continue;
          const val = row[metadataId];
          if (val === '' && !row.__modifiedCells.has(metadataId)) continue;

          const originalSnapshot = this.snapshots().find(
            (s) => s.timestamp === row.__originalTimestamp,
          );
          const hadValue = originalSnapshot && metadataId in originalSnapshot.values;

          if (hadValue) {
            updates.push({
              old_timestamp: row.__originalTimestamp,
              new_timestamp: newTs,
              metadata_id: metadataId,
              value: this.parseValue(val, field.value_type),
            });
          } else if (val !== '') {
            inserts.push({
              timestamp: newTs ?? row.__originalTimestamp,
              metadata_id: metadataId,
              value: this.parseValue(val, field.value_type),
            });
          }
        }
      }
    }

    this.save.emit({ updates, inserts, deletes });
  }

  // ─── Template helpers ─────────────────────────────────
  enumOptionsFor(field: MetadataFieldInfo): string[] {
    return (field.config?.['options'] as string[]) ?? [];
  }

  referenceOptionsFor(field: MetadataFieldInfo): { label: string; value: string }[] {
    return this.referenceOptions()[field.metadata_id] ?? [];
  }

  displayValue(row: GridRow, field: MetadataFieldInfo): string {
    const raw = row[field.metadata_id];
    if (raw == null || raw === '') return '';
    if (field.value_type === 'reference') {
      const opts = this.referenceOptions()[field.metadata_id] ?? [];
      const opt = opts.find((o) => o.value === raw);
      return opt ? opt.label : String(raw);
    }
    if (field.value_type === 'boolean') {
      return raw === 'true' ? 'True' : raw === 'false' ? 'False' : '';
    }
    return String(raw);
  }

  /** Convert an editor's raw output back to a canonical storage string so
   *  modified-vs-original comparisons stay consistent. */
  private formatForStorage(raw: any, valueType: string): string {
    if (raw == null || raw === '') return '';
    if (valueType === 'datetime' && raw instanceof Date) return raw.toISOString();
    if (valueType === 'date' && raw instanceof Date) {
      const y = raw.getFullYear();
      const m = String(raw.getMonth() + 1).padStart(2, '0');
      const d = String(raw.getDate()).padStart(2, '0');
      return `${y}-${m}-${d}`;
    }
    if (valueType === 'time' && raw instanceof Date) return raw.toTimeString().slice(0, 8);
    if (typeof raw === 'number') return String(raw);
    if (typeof raw === 'boolean') return raw ? 'true' : 'false';
    return String(raw);
  }

  // ─── Private helpers ──────────────────────────────────
  private buildRows(): GridRow[] {
    return this.snapshots().map((s, i) => {
      const row: GridRow = {
        __id: `ts:${s.timestamp}:${i}`,
        __originalTimestamp: s.timestamp,
        __isNew: false,
        __isDeleted: false,
        __modifiedCells: new Set<string>(),
        __timestampModified: false,
        __originalValues: {},
        timestamp: s.timestamp,
      };
      for (const [key, val] of Object.entries(s.values)) {
        const strVal =
          val === null || val === undefined
            ? ''
            : typeof val === 'object'
              ? JSON.stringify(val)
              : String(val);
        row[key] = strVal;
        row.__originalValues[key] = strVal;
      }
      for (const f of this.fields()) {
        if (!(f.metadata_id in s.values)) {
          row[f.metadata_id] = '';
          row.__originalValues[f.metadata_id] = '';
        }
      }
      return row;
    });
  }

  private updateChangeCount(): void {
    let count = 0;
    for (const row of this.rowData()) {
      if (row.__isNew) count++;
      else if (row.__isDeleted) count++;
      else if (row.__timestampModified) count++;
      else if (row.__modifiedCells.size > 0) count += row.__modifiedCells.size;
    }
    this.changeCount.set(count);
  }

  private parseValue(raw: any, valueType: string): any {
    if (raw == null || raw === '') return null;
    if (valueType === 'integer') {
      const n = parseInt(String(raw), 10);
      return isNaN(n) ? raw : n;
    }
    if (valueType === 'float') {
      const n = parseFloat(String(raw));
      return isNaN(n) ? raw : n;
    }
    if (valueType === 'boolean') {
      return String(raw) === 'true';
    }
    return typeof raw === 'string' ? raw : String(raw);
  }
}
