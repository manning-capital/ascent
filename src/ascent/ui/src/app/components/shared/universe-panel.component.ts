import { Component, computed, EventEmitter, inject, input, OnInit, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { Instrument, UniverseItem } from '../../models/asset.model';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, GridApi, GridReadyEvent, ICellRendererParams } from 'ag-grid-community';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { ThemeService } from '../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './data-table/ag-grid-theme';
import { badgeStyles } from './data-table/cell-renderers';
import { UniverseTableComponent } from './universe-table.component';

// ─── Stage/Unstage button cell renderer ─────────────────────
@Component({
  selector: 'ag-stage-cell',
  standalone: true,
  template: `
    @if (staged) {
      <button (click)="onClick($event)" class="text-xs text-green-500 hover:underline">Staged</button>
    } @else {
      <button (click)="onClick($event)" class="text-xs text-primary hover:underline">Add</button>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class StageCellRenderer implements ICellRendererAngularComp {
  staged = false;
  private params!: any;

  agInit(params: ICellRendererParams): void { this.params = params; this.staged = params.context?.isStaged(params.data?.id); }
  refresh(params: ICellRendererParams): boolean { this.params = params; this.staged = params.context?.isStaged(params.data?.id); return true; }

  onClick(e: Event): void {
    e.stopPropagation();
    this.params.context?.toggleStage(this.params.data?.id);
  }
}

// ─── Status badge cell renderer ─────────────────────────────
@Component({
  selector: 'ag-status-badge',
  standalone: true,
  template: `<span [style]="styles">{{ label }}</span>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class StatusBadgeCellRenderer implements ICellRendererAngularComp {
  label = ''; styles = '';
  agInit(p: ICellRendererParams): void { this.label = p.value ? 'Active' : 'Inactive'; this.styles = badgeStyles(p.value ? 'success' : 'secondary'); }
  refresh(p: ICellRendererParams): boolean { this.agInit(p); return true; }
}

@Component({
  selector: 'app-universe-panel',
  standalone: true,
  imports: [
    FormsModule,
    AgGridAngular,
    InputText,
    Select,
    Button,
    Card,
    UniverseTableComponent,
  ],
  template: `
    <div class="overflow-y-auto h-full p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-semibold text-sm">Instrument Universe</h3>
          <p class="text-xs text-surface-400 mt-1">{{ subtitle() }}</p>
        </div>
        @if (!showForm()) {
          <p-button label="+ Add Instruments" [outlined]="true" size="small" (onClick)="openForm()"/>
        }
      </div>

      <!-- Add Instruments Form -->
      @if (showForm()) {
        <p-card styleClass="mb-6">
          <ng-template #header>
            <div class="flex items-center justify-between px-5 pt-4">
              <div>
                <span class="font-semibold text-sm">Select Instruments</span>
                <span class="text-xs text-surface-400 ml-2">{{ stagedIds().size }} staged</span>
              </div>
              <div class="flex items-center gap-2">
                <p-button label="Cancel" severity="secondary" [text]="true" size="small" (onClick)="cancelForm()"/>
                <p-button
                  [label]="'Add ' + stagedIds().size + ' Instrument' + (stagedIds().size === 1 ? '' : 's')"
                  size="small"
                  (onClick)="submitStaged()"
                  [disabled]="stagedIds().size === 0"/>
              </div>
            </div>
          </ng-template>

          <!-- Filters -->
          <div class="flex items-center justify-between gap-4 mb-3">
            <div class="flex items-center gap-2 flex-1">
              <input type="text" pInputText placeholder="Search instruments..." (input)="onQuickFilter($any($event.target).value)" class="w-64"/>
              <p-select
                [(ngModel)]="typeFilter"
                [options]="typeFilterOptions()"
                optionLabel="label"
                optionValue="value"
                placeholder="All Types"
                [showClear]="true"
                (onChange)="applyExternalFilters()"
                appendTo="body"/>
              <p-select
                [(ngModel)]="statusFilter"
                [options]="statusFilterOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="All Statuses"
                [showClear]="true"
                (onChange)="applyExternalFilters()"
                appendTo="body"/>
            </div>
            <p-button
              label="Stage All Filtered"
              severity="secondary"
              [outlined]="true"
              size="small"
              (onClick)="stageAllFiltered()"/>
          </div>

          <!-- Available instruments AG Grid -->
          <div [attr.data-ag-theme-mode]="themeMode()" class="rounded-lg overflow-clip border border-edge">
            <ag-grid-angular
              [theme]="theme"
              [rowData]="availableInstruments()"
              [columnDefs]="availableColDefs"
              [defaultColDef]="defaultColDef"
              [domLayout]="'autoHeight'"
              [pagination]="true"
              [paginationPageSize]="10"
              [paginationPageSizeSelector]="[10, 25, 50]"
              [suppressCellFocus]="true"
              [isExternalFilterPresent]="isExternalFilterPresent"
              [doesExternalFilterPass]="doesExternalFilterPass"
              [getRowStyle]="getRowStyle"
              [context]="gridContext"
              (gridReady)="onGridReady($event)"/>
          </div>
        </p-card>
      }

      <!-- Universe Table -->
      <app-universe-table [items]="items()" (remove)="remove.emit($event)"/>
    </div>
  `,
})
export class UniversePanelComponent implements OnInit {
  assetService = inject(AssetService);
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;

  ngOnInit(): void {
    this.assetService.loadInstruments();
    this.assetService.loadInstrumentTypes();
  }

  items = input<UniverseItem[]>([]);
  subtitle = input('Instruments in this universe.');
  @Output() addInstruments = new EventEmitter<{ instrumentIds: string[]; startOrder: number }>();
  @Output() remove = new EventEmitter<string>();

  showForm = signal(false);
  stagedIds = signal<Set<string>>(new Set());
  private gridApi: GridApi | null = null;
  private quickFilterText = '';

  // Filters
  typeFilter = '';
  statusFilter: boolean | '' = '';

  statusFilterOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  defaultColDef: ColDef = {
    sortable: true,
    resizable: false,
    suppressMovable: true,
    flex: 1,
  };

  gridContext = {
    isStaged: (id: string) => this.stagedIds().has(id),
    toggleStage: (id: string) => {
      this.stagedIds.update(s => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id); else n.add(id);
        return n;
      });
      this.gridApi?.refreshCells({ force: true });
    },
  };

  availableColDefs: ColDef[] = [
    { headerName: 'Display Name', field: 'display_name' },
    { headerName: 'Name', field: 'name', cellClass: 'font-mono text-surface-500' },
    { headerName: 'Type', field: 'instrument_type_id', valueFormatter: (p) => this.getTypeName(p.value) },
    { headerName: 'Pair', field: 'pair', cellClass: 'font-mono text-surface-500', valueGetter: (p) => `${p.data?.from_asset_name ?? ''}/${p.data?.to_asset_name ?? ''}` },
    { headerName: 'Status', field: 'is_active', cellRenderer: StatusBadgeCellRenderer },
    { headerName: '', field: '', cellRenderer: StageCellRenderer, sortable: false, maxWidth: 80 },
  ];

  getRowStyle = (params: any) => {
    if (params.data && this.stagedIds().has(params.data.id)) {
      return { background: 'rgba(34, 197, 94, 0.05)' };
    }
    return undefined;
  };

  isExternalFilterPresent = (): boolean => {
    return this.typeFilter !== '' || this.statusFilter !== '';
  };

  doesExternalFilterPass = (node: any): boolean => {
    const data = node.data;
    if (!data) return true;
    if (this.typeFilter && data.instrument_type_id !== this.typeFilter) return false;
    if (this.statusFilter !== '' && data.is_active !== this.statusFilter) return false;
    return true;
  };

  /** Instruments not already in the universe. */
  availableInstruments = computed(() => {
    const existingIds = new Set(this.items().map(i => i.instrument_id));
    return this.assetService.instruments().filter(i => !existingIds.has(i.id));
  });

  typeFilterOptions = computed(() => {
    const types = this.assetService.instrumentTypes();
    return types.map(t => ({ label: t.display_name || t.name, value: t.id }));
  });

  getTypeName(typeId: string): string {
    return this.assetService.instrumentTypes().find(t => t.id === typeId)?.display_name ?? '';
  }

  onGridReady(event: GridReadyEvent): void {
    this.gridApi = event.api;
  }

  onQuickFilter(text: string): void {
    this.quickFilterText = text;
    this.gridApi?.setGridOption('quickFilterText', text);
  }

  applyExternalFilters(): void {
    this.gridApi?.onFilterChanged();
  }

  openForm(): void {
    this.stagedIds.set(new Set());
    this.typeFilter = '';
    this.statusFilter = '';
    this.quickFilterText = '';
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }

  stageAllFiltered(): void {
    this.stagedIds.update(s => {
      const n = new Set(s);
      this.gridApi?.forEachNodeAfterFilterAndSort(node => {
        if (node.data?.id) n.add(node.data.id);
      });
      return n;
    });
    this.gridApi?.refreshCells({ force: true });
  }

  submitStaged(): void {
    const ids = Array.from(this.stagedIds());
    if (ids.length === 0) return;
    this.addInstruments.emit({ instrumentIds: ids, startOrder: this.items().length + 1 });
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }
}
