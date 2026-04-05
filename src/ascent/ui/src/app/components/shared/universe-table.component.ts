import { Component, computed, inject, input, Output, EventEmitter } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { Button } from 'primeng/button';
import { EmptyStateComponent } from './empty-state.component';
import { AssetPairBadgeComponent, AssetPair } from './asset-pair-badge.component';
import { UniverseItem, Instrument } from '../../models/asset.model';
import { AssetService } from '../../services/asset.service';
import { ThemeService } from '../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from './data-table/ag-grid-theme';
import { badgeStyles } from './data-table/cell-renderers';

/** A row representing one instrument in the universe. */
interface UniverseRow {
  instrumentId: string;
  instrumentName: string;
  instrumentDisplayName: string;
  instrumentTypeId: string;
  isActive: boolean;
  pair: AssetPair | null;
  order: number;
}

// ─── Instrument cell (name + subtitle) ──────────────────────
@Component({
  selector: 'ag-instrument-cell',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div>
      <a [routerLink]="['/settings/instruments', instrumentId]" (click)="$event.stopPropagation()" class="text-primary hover:underline font-medium">{{ displayName || name }}</a>
      @if (displayName && name) {
        <div class="text-[0.6875rem] font-mono text-surface-400">{{ name }}</div>
      }
    </div>
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class InstrumentCellRenderer implements ICellRendererAngularComp {
  instrumentId = '';
  name = '';
  displayName = '';

  agInit(params: ICellRendererParams): void { this.update(params); }
  refresh(params: ICellRendererParams): boolean { this.update(params); return true; }

  private update(params: ICellRendererParams): void {
    const data = params.data as UniverseRow;
    this.instrumentId = data?.instrumentId ?? '';
    this.name = data?.instrumentName ?? '';
    this.displayName = data?.instrumentDisplayName ?? '';
  }
}

// ─── Pair cell ──────────────────────────────────────────────
@Component({
  selector: 'ag-pair-cell',
  standalone: true,
  imports: [AssetPairBadgeComponent],
  template: `@if (pair) { <app-asset-pair-badge [pairs]="[pair]" [maxVisible]="1"/> }`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class PairCellRenderer implements ICellRendererAngularComp {
  pair: AssetPair | null = null;

  agInit(params: ICellRendererParams): void { this.pair = params.data?.pair ?? null; }
  refresh(params: ICellRendererParams): boolean { this.pair = params.data?.pair ?? null; return true; }
}

// ─── Type link cell ─────────────────────────────────────────
@Component({
  selector: 'ag-type-link-cell',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (typeId) {
      <a [routerLink]="['/settings/instrument-types', typeId]" (click)="$event.stopPropagation()" class="text-primary hover:underline text-xs">{{ typeName }}</a>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class TypeLinkCellRenderer implements ICellRendererAngularComp {
  typeId = '';
  typeName = '';

  agInit(params: ICellRendererParams & { getTypeName?: (id: string) => string }): void { this.update(params); }
  refresh(params: ICellRendererParams & { getTypeName?: (id: string) => string }): boolean { this.update(params); return true; }

  private update(params: ICellRendererParams & { getTypeName?: (id: string) => string }): void {
    this.typeId = params.data?.instrumentTypeId ?? '';
    this.typeName = params.getTypeName?.(this.typeId) ?? '';
  }
}

// ─── Remove button cell ─────────────────────────────────────
@Component({
  selector: 'ag-remove-cell',
  standalone: true,
  imports: [Button],
  template: `<p-button label="Remove" severity="danger" [text]="true" size="small" (onClick)="onRemove($event)"/>`,
  host: { style: 'display:flex;align-items:center;justify-content:center;height:100%' },
})
export class RemoveCellRenderer implements ICellRendererAngularComp {
  private params!: any;

  agInit(params: any): void { this.params = params; }
  refresh(params: any): boolean { this.params = params; return true; }

  onRemove(e: Event): void {
    e.stopPropagation();
    this.params.context.componentParent.onRemove(this.params.data?.instrumentId);
  }
}

// ──�� Main component ─────────────────────────────────────────
@Component({
  selector: 'app-universe-table',
  standalone: true,
  imports: [AgGridAngular, EmptyStateComponent],
  template: `
    @if (rows().length === 0) {
      <app-empty-state title="No instruments" message="Add instruments to this universe." icon="data"/>
    } @else {
      <div [attr.data-ag-theme-mode]="themeMode()" class="rounded-lg overflow-clip border border-edge">
        <ag-grid-angular
          [theme]="theme"
          [rowData]="rows()"
          [columnDefs]="colDefs"
          [defaultColDef]="defaultColDef"
          [domLayout]="'autoHeight'"
          [pagination]="true"
          [paginationPageSize]="10"
          [paginationPageSizeSelector]="[5, 10, 25]"
          [suppressCellFocus]="true"
          [context]="gridContext"/>
      </div>
    }
  `,
})
export class UniverseTableComponent {
  private assetService = inject(AssetService);
  private themeSvc = inject(ThemeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;

  items = input<UniverseItem[]>([]);
  @Output() remove = new EventEmitter<string>();

  gridContext = { componentParent: this };

  defaultColDef: ColDef = {
    sortable: true,
    resizable: false,
    suppressMovable: true,
    flex: 1,
  };

  colDefs: ColDef[] = [
    { headerName: 'Instrument', field: 'instrumentDisplayName', cellRenderer: InstrumentCellRenderer, minWidth: 180 },
    { headerName: 'Pair', field: 'pair', cellRenderer: PairCellRenderer, sortable: false, minWidth: 200 },
    { headerName: 'Instrument Type', field: 'instrumentTypeId', cellRenderer: TypeLinkCellRenderer, cellRendererParams: { getTypeName: (id: string) => this.getTypeDisplayName(id) } },
    { headerName: 'Status', field: 'isActive', cellRenderer: 'statusRenderer', width: 96, maxWidth: 96, flex: 0 },
    { headerName: '', field: '', cellRenderer: RemoveCellRenderer, width: 80, maxWidth: 80, flex: 0, sortable: false },
  ];

  // Register the status renderer inline
  constructor() {
    // Replace the string ref with the actual renderer
    const statusCol = this.colDefs.find(c => c.cellRenderer === 'statusRenderer');
    if (statusCol) {
      statusCol.cellRenderer = StatusTagRenderer;
    }
  }

  rows = computed<UniverseRow[]>(() => {
    const instruments = this.assetService.instruments();
    const instrumentMap = new Map<string, Instrument>();
    for (const inst of instruments) instrumentMap.set(inst.id, inst);

    return this.items().map(item => {
      const inst = instrumentMap.get(item.instrument_id);
      const pair: AssetPair | null = inst ? {
        providerName: inst.provider_name ?? '',
        providerId: inst.provider_id,
        fromAssetName: inst.from_asset_name ?? '',
        fromAssetId: inst.from_asset_id,
        toAssetName: inst.to_asset_name ?? '',
        toAssetId: inst.to_asset_id,
      } : null;
      return {
        instrumentId: item.instrument_id,
        instrumentName: item.instrument_name ?? inst?.name ?? item.instrument_id,
        instrumentDisplayName: item.instrument_display_name ?? inst?.display_name ?? '',
        instrumentTypeId: item.instrument_type_id ?? inst?.instrument_type_id ?? '',
        isActive: item.is_active ?? inst?.is_active ?? true,
        pair,
        order: item.order,
      };
    }).sort((a, b) => a.order - b.order);
  });

  getTypeDisplayName(typeId: string): string {
    if (!typeId) return '';
    const t = this.assetService.instrumentTypes().find(t => t.id === typeId);
    return t?.display_name || t?.name || '';
  }

  onRemove(instrumentId: string): void {
    this.remove.emit(instrumentId);
  }
}

// ─── Inline status tag renderer ─────────────────────────────
@Component({
  selector: 'ag-status-tag',
  standalone: true,
  template: `<span [style]="styles">{{ label }}</span>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
class StatusTagRenderer implements ICellRendererAngularComp {
  label = '';
  styles = '';

  agInit(params: ICellRendererParams): void { this.update(params); }
  refresh(params: ICellRendererParams): boolean { this.update(params); return true; }

  private update(params: ICellRendererParams): void {
    this.label = params.value ? 'Active' : 'Inactive';
    this.styles = badgeStyles(params.value ? 'success' : 'secondary');
  }
}
