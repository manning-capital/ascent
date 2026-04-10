import { Component, input, output, inject, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, GridApi, ICellRendererParams, RowClickedEvent } from 'ag-grid-community';
import { Card } from 'primeng/card';
import { TradeListItem, TradeLegSummary } from '../../models/trade.model';
import { TradeService } from '../../services/trade.service';
import type { ServerFetchFn } from '../shared/data-table/data-table.model';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';
import { EmptyStateComponent } from '../shared/empty-state.component';
import { ThemeService } from '../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from '../shared/data-table/ag-grid-theme';
import { badgeStyles } from '../shared/data-table/cell-renderers';
import { ServerTableComponent } from '../shared/data-table/server-table.component';

function tagSeverity(label: string): string {
  switch (label.toUpperCase()) {
    case 'LONG': case 'ENTRY': case 'COMPLETED': case 'BUY': return 'success';
    case 'SHORT': case 'FAILED': case 'STOP_LOSS': case 'SELL': return 'danger';
    case 'COMPOUND': case 'RUNNING': case 'TAKE_PROFIT': return 'warn';
    case 'PAPER': case 'EXIT': return 'contrast';
    default: return 'secondary';
  }
}

function statusSeverity(label: string): string {
  switch (label.toUpperCase()) {
    case 'OPEN': case 'FILLED': return 'success';
    case 'OPENING': case 'CLOSING': case 'PARTIALLY_FILLED': return 'contrast';
    case 'PENDING': case 'SUBMITTED': case 'ACCEPTED': return 'warn';
    case 'ERROR': case 'REJECTED': return 'danger';
    case 'CLOSED': case 'CANCELLED': return 'secondary';
    default: return 'warn';
  }
}

// ─── Symbol cell (name + optional PAPER badge) ──────────────
@Component({
  selector: 'ag-symbol-cell',
  standalone: true,
  template: `
    <div class="flex items-center gap-2">
      <span class="font-medium text-sm">{{ symbol }}</span>
      @if (isPaper) { <span [style]="paperStyles">PAPER</span> }
    </div>
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class SymbolCellRenderer implements ICellRendererAngularComp {
  symbol = ''; isPaper = false;
  paperStyles = badgeStyles('contrast');
  agInit(p: ICellRendererParams): void { this.symbol = p.data?.display_symbol ?? ''; this.isPaper = !!p.data?.is_paper; }
  refresh(p: ICellRendererParams): boolean { this.agInit(p); return true; }
}

// ─── Tags cell (multiple badges) ────────────────────────────
@Component({
  selector: 'ag-tags-cell',
  standalone: true,
  template: `<div class="flex gap-1">@for (t of tagData; track t.label) { <span [style]="t.styles">{{ t.label }}</span> }</div>`,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class TagsCellRenderer implements ICellRendererAngularComp {
  tagData: { label: string; styles: string }[] = [];
  agInit(p: ICellRendererParams): void { this.update(p); }
  refresh(p: ICellRendererParams): boolean { this.update(p); return true; }
  private update(p: ICellRendererParams): void {
    this.tagData = (p.data?.tags ?? [])
      .filter((t: string) => t !== 'PAPER')
      .map((t: string) => ({ label: t, styles: badgeStyles(tagSeverity(t)) }));
  }
}

// ─── Status badge cell ──────────────────────────────────────
@Component({
  selector: 'ag-trade-status-cell',
  standalone: true,
  template: `@if (status) { <span [style]="styles">{{ status }}</span> }`,
  host: { style: 'display:flex;align-items:center;justify-content:flex-end;height:100%;width:100%' },
})
export class TradeStatusCellRenderer implements ICellRendererAngularComp {
  status = ''; styles = '';
  agInit(p: ICellRendererParams): void { this.status = p.data?.current_status ?? ''; this.styles = this.status ? badgeStyles(statusSeverity(this.status)) : ''; }
  refresh(p: ICellRendererParams): boolean { this.agInit(p); return true; }
}

// ─── P&L cell with color ────────────────────────────────────
@Component({
  selector: 'ag-trade-pnl-cell',
  standalone: true,
  template: `<span [class]="pnlClass" class="text-sm">{{ formatted }}</span>`,
  host: { style: 'display:flex;align-items:center;justify-content:flex-end;height:100%;width:100%' },
})
export class TradePnlCellRenderer implements ICellRendererAngularComp {
  formatted = ''; pnlClass = '';
  agInit(p: ICellRendererParams & { tradeService?: TradeService }): void { this.update(p); }
  refresh(p: ICellRendererParams & { tradeService?: TradeService }): boolean { this.update(p); return true; }
  private update(p: ICellRendererParams & { tradeService?: TradeService }): void {
    const svc = p.tradeService;
    const val = p.data?.total_realized_pnl;
    this.formatted = svc?.formatCurrency(val) ?? '';
    this.pnlClass = svc?.getPnlClass(val) ?? '';
  }
}

@Component({
  selector: 'app-trade-table',
  standalone: true,
  imports: [BadgeComponent, StatCardComponent, AgGridAngular, ServerTableComponent, Card, EmptyStateComponent],
  templateUrl: './trade-table.component.html',
})
export class TradeTableComponent {
  private router = inject(Router);
  private themeSvc = inject(ThemeService);
  tradeService = inject(TradeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;

  trades = input<TradeListItem[]>([]);
  showStrategy = input(true);
  loading = input(false);
  pageSize = input(25);
  page = input(1);
  totalPages = input(1);
  pageChange = output<number>();
  fetchPage = input<ServerFetchFn<TradeListItem> | null>(null);
  showPaginator = input(true);

  private gridApi: GridApi | null = null;

  // Server-side outputs (delegated to ServerTableComponent)
  sortChange = output<{ field: string; order: string }>();
  pageSizeChange = output<number>();
  serverPageChange = output<number>();

  // Mobile data from ServerTableComponent's dataLoaded output
  _serverRowData = signal<TradeListItem[]>([]);
  /** Trades to display in mobile view: from fetchPage or from input. */
  displayTrades = computed(() => this.fetchPage() ? this._serverRowData() : this.trades());

  /** Route builder for server-table row clicks. */
  navigateToTradeRoute = (trade: TradeListItem) => ['/trades', trade.id];

  onDataLoaded(items: TradeListItem[]): void {
    this._serverRowData.set(items);
  }

  colDefs = computed<ColDef[]>(() => {
    const cols: ColDef[] = [
      { headerName: 'Symbol', field: 'display_symbol', cellRenderer: SymbolCellRenderer, sortable: false, minWidth: 140 },
    ];
    if (this.showStrategy()) {
      cols.push({ headerName: 'Strategy', field: 'strategy_name', sortable: false, cellClass: 'text-sm text-surface-500' });
    }
    cols.push(
      { headerName: 'Type', field: 'tags', cellRenderer: TagsCellRenderer, sortable: false, minWidth: 120 },
      { headerName: 'Qty', field: 'qty', sortable: false, valueGetter: (p) => { const leg = p.data?.legs?.[0]; return leg?.quantity ?? null; }, valueFormatter: (p) => p.value != null ? new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 }).format(p.value) : '', cellClass: 'text-sm' },
      { headerName: 'Entry Price', field: 'entry', sortable: false, valueGetter: (p) => p.data?.legs?.[0]?.entry_price ?? null, valueFormatter: (p) => this.tradeService.formatCurrency(p.value), cellClass: 'text-sm' },
      { headerName: 'Exit/Current', field: 'exit', sortable: false, valueGetter: (p) => { const leg = p.data?.legs?.[0]; return leg?.exit_price ?? leg?.entry_price ?? null; }, valueFormatter: (p) => this.tradeService.formatCurrency(p.value), cellClass: 'text-sm' },
      { headerName: 'P&L', field: 'total_realized_pnl', cellRenderer: TradePnlCellRenderer, cellRendererParams: { tradeService: this.tradeService } },
      { headerName: 'Status', field: 'current_status', sortable: false, cellRenderer: TradeStatusCellRenderer },
    );
    return cols;
  });

  defaultColDef: ColDef = {
    sortable: true,
    resizable: false,
    suppressMovable: true,
    flex: 1,
    comparator: () => 0,
  };

  onGridReady(event: { api: GridApi }): void {
    this.gridApi = event.api;
  }

  onRowClicked(event: RowClickedEvent): void {
    if (event.data?.id) {
      this.router.navigate(['/trades', event.data.id]);
    }
  }

  navigateToTrade(tradeId: string): void {
    this.router.navigate(['/trades', tradeId]);
  }

  onPageChange(newPage: number): void {
    this.pageChange.emit(newPage);
  }

  getMainLeg(trade: TradeListItem): TradeLegSummary | null {
    return trade.legs.length > 0 ? trade.legs[0] : null;
  }
}
