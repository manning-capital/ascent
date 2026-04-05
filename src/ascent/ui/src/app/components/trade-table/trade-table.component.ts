import { Component, input, output, inject, computed } from '@angular/core';
import { Router } from '@angular/router';
import { AgGridAngular } from 'ag-grid-angular';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ColDef, ICellRendererParams, RowClickedEvent } from 'ag-grid-community';
import { Card } from 'primeng/card';
import { TradeListItem, TradeLegSummary } from '../../models/trade.model';
import { TradeService } from '../../services/trade.service';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';
import { EmptyStateComponent } from '../shared/empty-state.component';
import { ThemeService } from '../../services/theme.service';
import { AG_GRID_THEME, agThemeMode } from '../shared/data-table/ag-grid-theme';
import { badgeStyles } from '../shared/data-table/cell-renderers';

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
  imports: [BadgeComponent, StatCardComponent, AgGridAngular, Card, EmptyStateComponent],
  templateUrl: './trade-table.component.html',
})
export class TradeTableComponent {
  private router = inject(Router);
  private themeSvc = inject(ThemeService);
  tradeService = inject(TradeService);
  themeMode = agThemeMode(this.themeSvc);
  theme = AG_GRID_THEME;

  trades = input.required<TradeListItem[]>();
  showStrategy = input(true);
  loading = input(false);
  pageSize = input(10);
  page = input(1);
  totalPages = input(1);
  pageChange = output<number>();

  colDefs = computed<ColDef[]>(() => {
    const cols: ColDef[] = [
      { headerName: 'Symbol', field: 'display_symbol', cellRenderer: SymbolCellRenderer, minWidth: 140 },
    ];
    if (this.showStrategy()) {
      cols.push({ headerName: 'Strategy', field: 'strategy_name', cellClass: 'text-sm text-surface-500' });
    }
    cols.push(
      { headerName: 'Type', field: 'tags', cellRenderer: TagsCellRenderer, sortable: false, minWidth: 120 },
      { headerName: 'Qty', field: 'qty', valueGetter: (p) => { const leg = p.data?.legs?.[0]; return leg?.quantity ?? null; }, valueFormatter: (p) => p.value != null ? new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 }).format(p.value) : '', cellClass: 'text-sm' },
      { headerName: 'Entry Price', field: 'entry', valueGetter: (p) => p.data?.legs?.[0]?.entry_price ?? null, valueFormatter: (p) => this.tradeService.formatCurrency(p.value), cellClass: 'text-sm' },
      { headerName: 'Exit/Current', field: 'exit', valueGetter: (p) => { const leg = p.data?.legs?.[0]; return leg?.exit_price ?? leg?.entry_price ?? null; }, valueFormatter: (p) => this.tradeService.formatCurrency(p.value), cellClass: 'text-sm' },
      { headerName: 'P&L', field: 'total_realized_pnl', cellRenderer: TradePnlCellRenderer, cellRendererParams: { tradeService: this.tradeService } },
      { headerName: 'Status', field: 'current_status', cellRenderer: TradeStatusCellRenderer },
    );
    return cols;
  });

  defaultColDef: ColDef = {
    sortable: true,
    resizable: false,
    suppressMovable: true,
    flex: 1,
  };

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
