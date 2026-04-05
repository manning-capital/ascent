import { Component, inject, input, output, signal, computed, effect, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MetadataFieldInfo,
  MetadataSnapshotRow,
  BulkHistoryUpdate,
  BulkHistoryUpdateEntry,
  BulkHistoryInsertEntry,
  BulkHistoryDeleteEntry,
} from '../../models/asset.model';
import { ThemeService } from '../../services/theme.service';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp, ICellEditorAngularComp } from 'ag-grid-angular';
import { TrashIcon } from 'primeng/icons/trash';
import { UndoIcon } from 'primeng/icons/undo';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import {
  type ColDef,
  type GridApi,
  type GridReadyEvent,
  type CellValueChangedEvent,
  type GetRowIdParams,
  type CellStyleFunc,
} from 'ag-grid-community';
import { AG_GRID_THEME, agThemeMode } from './data-table/ag-grid-theme';

function formatLocalDateTime(d: Date): string {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const mo = months[d.getMonth()];
  const day = d.getDate();
  const y = d.getFullYear();
  const h = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${mo} ${day}, ${y} ${h}:${mi}:${s}`;
}

// ─── Row shape ───────────────────────────────────────────
interface GridRow {
  __id: string;
  __originalTimestamp: string;
  __isNew: boolean;
  __isDeleted: boolean;
  __modifiedCells: Set<string>;
  __timestampModified: boolean;
  __originalValues: Record<string, string>;
  timestamp: string;
  [key: string]: any;
}

// ─── Shared styles for PrimeNG cell editors inside AG Grid
const agSelectStyles = `
  :host {
    display: flex; align-items: center; width: 100%; height: 100%; overflow: visible;
    padding-left: var(--ag-cell-horizontal-padding, 12px);
    background: var(--ag-background-color);
  }
  :host ::ng-deep .ag-cell-select { width: 100%; border: none; }
  :host ::ng-deep .ag-cell-select .p-select {
    border: none; border-radius: 0; background: transparent; box-shadow: none;
    min-height: unset; height: 100%; padding: 0; font-size: inherit;
  }
  :host ::ng-deep .ag-cell-select .p-select-label { font-size: inherit; padding: 0; }
`;

const agDatePickerStyles = `
  :host { display: flex; align-items: center; width: 100%; height: 100%; overflow: visible; }
  :host ::ng-deep .ag-cell-date { width: 100%; }
  :host ::ng-deep .ag-cell-date .p-datepicker {
    border: none; border-radius: 0; background: transparent; box-shadow: none;
    min-height: unset; height: 100%; font-size: inherit;
  }
  :host ::ng-deep .ag-cell-date .p-datepicker input {
    border: none; background: transparent; box-shadow: none; padding: 0 0.5rem;
    font-size: inherit; height: 100%;
  }
`;

// ─── Custom cell editor for reference fields (searchable) ─
@Component({
  selector: 'ref-cell-editor',
  standalone: true,
  imports: [FormsModule, Select],
  template: `
    <p-select
      #sel
      [ngModel]="value"
      (ngModelChange)="onSelect($event)"
      [options]="options"
      optionLabel="label"
      optionValue="value"
      [filter]="true"
      filterPlaceholder="Search..."
      [appendTo]="'body'"
      placeholder="Select..."
      styleClass="ag-cell-select"
      (onHide)="onDropdownClose()"/>
  `,
  styles: [agSelectStyles],
})
export class RefCellEditorComponent implements ICellEditorAngularComp {
  @ViewChild('sel') selectEl!: Select;
  value: string = '';
  options: { label: string; value: string }[] = [];
  private params!: any;
  private committed = false;

  agInit(params: any): void {
    this.params = params;
    this.value = params.value ?? '';
    this.options = [{ label: '(none)', value: '' }, ...(params.options ?? [])];
    setTimeout(() => this.selectEl?.show());
  }

  getValue(): string {
    return this.value;
  }

  isPopup(): boolean {
    return false;
  }

  onSelect(val: string): void {
    this.value = val;
    this.committed = true;
    this.params.stopEditing();
  }

  onDropdownClose(): void {
    if (!this.committed) {
      this.params.stopEditing(true); // cancel — keep old value
    }
  }
}

// ─── Custom cell editor for date fields (PrimeNG DatePicker) ─
@Component({
  selector: 'date-cell-editor',
  standalone: true,
  imports: [FormsModule, DatePicker],
  template: `
    <p-datepicker
      #dp
      [(ngModel)]="dateValue"
      dateFormat="yy-mm-dd"
      [appendTo]="'body'"
      [style]="{ width: '100%' }"
      styleClass="ag-cell-date"
      (onSelect)="onSelect()"
      (onClose)="onClose()"/>
  `,
  styles: [agDatePickerStyles],
})
export class DateCellEditorComponent implements ICellEditorAngularComp {
  @ViewChild('dp') datePicker!: DatePicker;
  dateValue: Date | null = null;
  private params!: any;
  private committed = false;

  agInit(params: any): void {
    this.params = params;
    const v = params.value;
    if (v) {
      const parts = String(v).substring(0, 10).split('-');
      this.dateValue = new Date(+parts[0], +parts[1] - 1, +parts[2]);
    }
  }

  afterGuiAttached(): void {
    // DatePicker needs a tick to be fully initialized, then click its input to open
    setTimeout(() => {
      const input = this.datePicker?.el?.nativeElement?.querySelector('input');
      input?.click();
    });
  }

  getValue(): string {
    if (!this.dateValue) return '';
    const y = this.dateValue.getFullYear();
    const m = String(this.dateValue.getMonth() + 1).padStart(2, '0');
    const d = String(this.dateValue.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  isPopup(): boolean {
    return false;
  }

  onSelect(): void {
    this.committed = true;
    this.params.stopEditing();
  }

  onClose(): void {
    if (!this.committed) {
      this.params.stopEditing(true);
    }
  }
}

// ─── Custom cell editor for datetime fields (PrimeNG DatePicker + time) ─
@Component({
  selector: 'datetime-cell-editor',
  standalone: true,
  imports: [FormsModule, DatePicker],
  template: `
    <p-datepicker
      #dp
      [(ngModel)]="dateValue"
      [showTime]="true"
      [showSeconds]="true"
      dateFormat="yy-mm-dd"
      hourFormat="24"
      [appendTo]="'body'"
      [style]="{ width: '100%' }"
      styleClass="ag-cell-date"
      (onSelect)="onSelect()"
      (onClose)="onClose()"/>
  `,
  styles: [agDatePickerStyles],
})
export class DateTimeCellEditorComponent implements ICellEditorAngularComp {
  @ViewChild('dp') datePicker!: DatePicker;
  dateValue: Date | null = null;
  private params!: any;
  private originalValue = '';
  private userSelected = false;
  private committed = false;

  agInit(params: any): void {
    this.params = params;
    this.originalValue = params.value ?? '';
    const v = params.value;
    if (v) {
      this.dateValue = new Date(v);
      if (isNaN(this.dateValue.getTime())) this.dateValue = null;
    }
  }

  afterGuiAttached(): void {
    setTimeout(() => {
      const input = this.datePicker?.el?.nativeElement?.querySelector('input');
      input?.click();
    });
  }

  getValue(): string {
    if (!this.userSelected) return this.originalValue;
    if (!this.dateValue) return '';
    return formatLocalDateTime(this.dateValue);
  }

  isPopup(): boolean {
    return false;
  }

  onSelect(): void {
    this.userSelected = true;
  }

  onClose(): void {
    if (this.userSelected) {
      this.params.stopEditing();
    } else {
      this.params.stopEditing(true);
    }
  }
}

// ─── Custom cell editor for enum fields (PrimeNG Select) ─
@Component({
  selector: 'enum-cell-editor',
  standalone: true,
  imports: [FormsModule, Select],
  template: `
    <p-select
      #sel
      [ngModel]="value"
      (ngModelChange)="onSelect($event)"
      [options]="options"
      [appendTo]="'body'"
      placeholder="Select..."
      styleClass="ag-cell-select"
      (onHide)="onDropdownClose()"/>
  `,
  styles: [agSelectStyles],
})
export class EnumCellEditorComponent implements ICellEditorAngularComp {
  @ViewChild('sel') selectEl!: Select;
  value: string = '';
  options: string[] = [];
  private params!: any;
  private committed = false;

  agInit(params: any): void {
    this.params = params;
    this.value = params.value ?? '';
    this.options = ['', ...(params.values ?? [])];
    setTimeout(() => this.selectEl?.show());
  }

  getValue(): string {
    return this.value;
  }

  isPopup(): boolean {
    return false;
  }

  onSelect(val: string): void {
    this.value = val;
    this.committed = true;
    this.params.stopEditing();
  }

  onDropdownClose(): void {
    if (!this.committed) {
      this.params.stopEditing(true);
    }
  }
}

// ─── Custom cell renderer for actions column ─────────────
@Component({
  selector: 'action-cell',
  standalone: true,
  imports: [TrashIcon, UndoIcon],
  template: `
    @if (isDeleted) {
      <button (click)="onUndelete($event)" style="background:none;border:none;cursor:pointer" title="Undo delete">
        <svg data-p-icon="undo" />
      </button>
    } @else {
      <button (click)="onDelete($event)" style="background:none;border:none;cursor:pointer;color:var(--p-red-400)" title="Delete row">
        <svg data-p-icon="trash" />
      </button>
    }
  `,
  host: { style: 'display:flex;align-items:center;justify-content:center;height:100%' },
})
export class ActionCellRendererComponent implements ICellRendererAngularComp {
  isDeleted = false;
  private params!: any;

  agInit(params: any): void {
    this.params = params;
    this.isDeleted = !!params.data?.__isDeleted;
  }

  refresh(params: any): boolean {
    this.params = params;
    this.isDeleted = !!params.data?.__isDeleted;
    return true;
  }

  onDelete(e: Event): void {
    e.stopPropagation();
    this.params.context.componentParent.deleteRow(this.params.node);
  }

  onUndelete(e: Event): void {
    e.stopPropagation();
    this.params.context.componentParent.undeleteRow(this.params.node);
  }
}

// ─── Main component ──────────────────────────────────────
@Component({
  selector: 'app-metadata-history-table',
  standalone: true,
  imports: [AgGridAngular, Button, Tag],
  host: { class: 'block' },
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

    <!-- AG Grid -->
    <div [attr.data-ag-theme-mode]="themeMode()" class="rounded-lg overflow-clip border border-edge"
         [style.height.px]="gridHeight()">
      <ag-grid-angular
        style="width: 100%; height: 100%"
        [theme]="theme"
        [loading]="loading()"
        [rowData]="rowData()"
        [columnDefs]="colDefs()"
        [defaultColDef]="defaultColDef"
        [rowHeight]="48"
        [headerHeight]="48"
        [getRowId]="getRowId"
        [getRowStyle]="getRowStyle"
        [context]="gridContext"
        [singleClickEdit]="true"
        [suppressCellFocus]="true"
        [overlayNoRowsTemplate]="noRowsTemplate"
        (gridReady)="onGridReady($event)"
        (cellValueChanged)="onCellValueChanged($event)"/>
    </div>
  `,
})
export class MetadataHistoryTableComponent {
  // ─── Inputs / Outputs (same API as before) ─────────────
  fields = input.required<MetadataFieldInfo[]>();
  snapshots = input.required<MetadataSnapshotRow[]>();
  referenceOptions = input<Record<string, { label: string; value: string }[]>>({});
  loading = input(false);
  save = output<BulkHistoryUpdate>();

  // ─── Theme (shared across all AG Grid tables) ──
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;

  defaultColDef: ColDef = {
    sortable: true,
    filter: false,
    resizable: false,
    suppressMovable: true,
    flex: 1,
  };

  noRowsTemplate =
    '<span style="font-size: 12px; opacity: 0.5;">No history entries. Click + Insert Row to add one.</span>';
  gridContext = { componentParent: this };
  getRowId = (params: GetRowIdParams) => params.data.__id;

  getRowStyle = (params: any) => {
    if (params.data?.__isDeleted) {
      return { opacity: '0.4', textDecoration: 'line-through' };
    }
    return undefined;
  };

  // ─── State ─────────────────────────────────────────────
  rowData = signal<GridRow[]>([]);
  changeCount = signal(0);

  /** Grid height: header (48px) + rows (48px each) + borders (4px buffer), capped at 600px. */
  gridHeight = computed(() => {
    const headerHeight = 48;
    const rowHeight = 48;
    const rows = this.rowData().length;
    const natural = headerHeight + Math.max(rows, 1) * rowHeight + 4;
    return Math.min(natural, 600);
  });

  private gridApi: GridApi | null = null;
  private newRowCounter = 0;
  private initialized = false;

  constructor() {
    // Re-render cells when reference options arrive asynchronously
    effect(() => {
      this.referenceOptions(); // track
      this.gridApi?.refreshCells({ force: true });
    });
  }

  // ─── Computed column definitions ───────────────────────
  colDefs = computed<ColDef[]>(() => {
    const fields = this.fields();
    const refOpts = this.referenceOptions();

    const cellStyle: CellStyleFunc = (params) => {
      const data = params.data as GridRow;
      if (!data) return null;
      if (data.__isNew) return { backgroundColor: 'rgba(59, 130, 246, 0.1)' };
      const field = params.colDef?.field;
      if (field === 'timestamp' && data.__timestampModified) {
        return { backgroundColor: 'rgba(59, 130, 246, 0.1)' };
      }
      if (field && data.__modifiedCells?.has(field)) {
        return { backgroundColor: 'rgba(59, 130, 246, 0.1)' };
      }
      return null;
    };

    const editableWhenNotDeleted = (params: any) => !params.data?.__isDeleted;

    return [
      {
        headerName: 'Timestamp',
        field: 'timestamp',
        pinned: 'left' as const,
        width: 220,
        editable: editableWhenNotDeleted,
        cellEditor: DateTimeCellEditorComponent,
        cellStyle,
        valueFormatter: (params: any) => {
          const v = params.value;
          if (!v) return '';
          const d = new Date(v);
          if (isNaN(d.getTime())) return v;
          return formatLocalDateTime(d);
        },
      },
      ...fields.map((f): ColDef => {
        const base: ColDef = {
          headerName: f.metadata_display_name,
          field: f.metadata_id,
          minWidth: 140,
          editable: editableWhenNotDeleted,
          cellStyle,
        };

        switch (f.value_type) {
          case 'boolean':
            return {
              ...base,
              cellEditor: 'agSelectCellEditor',
              cellEditorParams: { values: ['', 'true', 'false'] },
            };
          case 'integer':
            return {
              ...base,
              cellEditor: 'agNumberCellEditor',
              cellEditorParams: { step: 1 },
              valueGetter: (p) => {
                const v = p.data?.[f.metadata_id];
                return v === '' || v == null ? null : Number(v);
              },
              valueSetter: (p) => {
                p.data[f.metadata_id] = p.newValue == null ? '' : String(p.newValue);
                return true;
              },
            };
          case 'float':
            return {
              ...base,
              cellEditor: 'agNumberCellEditor',
              cellEditorParams: { step: 0.001 },
              valueGetter: (p) => {
                const v = p.data?.[f.metadata_id];
                return v === '' || v == null ? null : Number(v);
              },
              valueSetter: (p) => {
                p.data[f.metadata_id] = p.newValue == null ? '' : String(p.newValue);
                return true;
              },
            };
          case 'date':
            return {
              ...base,
              cellEditor: DateCellEditorComponent,
              valueGetter: (p) => {
                const v = p.data?.[f.metadata_id];
                if (!v) return '';
                return String(v).substring(0, 10);
              },
              valueSetter: (p) => {
                p.data[f.metadata_id] = p.newValue
                  ? String(p.newValue).substring(0, 10)
                  : '';
                return true;
              },
            };
          case 'time':
            return { ...base, cellEditor: 'agTextCellEditor' };
          case 'datetime':
            return { ...base, cellEditor: DateTimeCellEditorComponent };
          case 'enum':
            return {
              ...base,
              cellEditor: EnumCellEditorComponent,
              cellEditorParams: {
                values: (f.config?.['options'] as string[]) ?? [],
              },
            };
          case 'reference': {
            const metaId = f.metadata_id;
            return {
              ...base,
              cellEditor: RefCellEditorComponent,
              cellEditorParams: () => ({
                options: this.referenceOptions()[metaId] ?? [],
              }),
              valueFormatter: (p: any) => {
                const opts = this.referenceOptions()[metaId] ?? [];
                const opt = opts.find((o: any) => o.value === p.value);
                return opt ? opt.label : (p.value || '');
              },
            };
          }
          default:
            return { ...base, cellEditor: 'agTextCellEditor' };
        }
      }),
      {
        headerName: '',
        pinned: 'right' as const,
        width: 60,
        maxWidth: 60,
        editable: false,
        sortable: false,
        cellRenderer: ActionCellRendererComponent,
      },
    ];
  });

  // ─── Lifecycle ─────────────────────────────────────────
  ngOnChanges(): void {
    if (!this.initialized || this.changeCount() === 0) {
      this.rowData.set(this.buildRows());
      this.updateChangeCount();
      this.initialized = true;
    }
  }

  onGridReady(event: GridReadyEvent): void {
    this.gridApi = event.api;
  }

  onCellValueChanged(event: CellValueChangedEvent): void {
    const data = event.data as GridRow;
    const field = event.colDef.field;
    if (!field || data.__isNew) {
      this.updateChangeCount();
      return;
    }

    if (field === 'timestamp') {
      data.__timestampModified = data.timestamp !== data.__originalTimestamp;
    } else {
      const original = data.__originalValues[field] ?? '';
      const current = String(data[field] ?? '');
      if (current !== original) {
        data.__modifiedCells.add(field);
      } else {
        data.__modifiedCells.delete(field);
      }
    }

    this.gridApi?.refreshCells({ force: true });
    this.updateChangeCount();
  }

  // ─── Row operations ────────────────────────────────────
  addRow(): void {
    const newRow: GridRow = {
      __id: `new-${this.newRowCounter++}`,
      __originalTimestamp: '',
      __isNew: true,
      __isDeleted: false,
      __modifiedCells: new Set<string>(),
      __timestampModified: false,
      __originalValues: {},
      timestamp: (() => { const d = new Date(); d.setHours(0, 0, 0, 0); return formatLocalDateTime(d); })(),
    };
    for (const f of this.fields()) {
      newRow[f.metadata_id] = '';
    }
    this.rowData.update((rows) => [newRow, ...rows]);
    this.updateChangeCount();
  }

  deleteRow(node: any): void {
    const data = node.data as GridRow;
    if (data.__isNew) {
      this.rowData.update((rows) => rows.filter((r) => r.__id !== data.__id));
    } else {
      data.__isDeleted = true;
      this.gridApi?.redrawRows({ rowNodes: [node] });
    }
    this.updateChangeCount();
  }

  undeleteRow(node: any): void {
    const data = node.data as GridRow;
    data.__isDeleted = false;
    this.gridApi?.redrawRows({ rowNodes: [node] });
    this.updateChangeCount();
  }

  discard(): void {
    this.newRowCounter = 0;
    this.rowData.set(this.buildRows());
    this.updateChangeCount();
  }

  // ─── Save logic (matches original) ────────────────────
  emitSave(): void {
    this.gridApi?.stopEditing();

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

  // ─── Private helpers ───────────────────────────────────
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
    if (valueType === 'date') {
      if (raw instanceof Date) {
        const y = raw.getFullYear();
        const m = String(raw.getMonth() + 1).padStart(2, '0');
        const d = String(raw.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
      }
      return String(raw);
    }
    if (valueType === 'datetime') {
      if (raw instanceof Date) return raw.toISOString();
      return String(raw);
    }
    if (valueType === 'time') {
      if (raw instanceof Date) return raw.toTimeString().slice(0, 8);
      return String(raw);
    }
    return typeof raw === 'string' ? raw : String(raw);
  }
}
