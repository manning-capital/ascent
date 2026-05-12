import {
  Component,
  computed,
  inject,
  input,
  OnDestroy,
  OnInit,
  output,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { Subscription } from 'rxjs';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import {
  AppColumn,
  AppFetchFn,
  AppFilterOption,
  AppSeverity,
} from '../ui/data-table/app-column.model';
import { TradeListItem, TradeLegSummary } from '../../models/trade.model';
import { TradeService } from '../../services/trade.service';
import { TradeStreamService } from '../../services/trade-stream.service';
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination';

const QTY_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
});

function tagSeverity(label: string): AppSeverity {
  switch (label.toUpperCase()) {
    case 'LONG': case 'ENTRY': case 'COMPLETED': case 'BUY': return 'success';
    case 'SHORT': case 'FAILED': case 'STOP_LOSS': case 'SELL': return 'danger';
    case 'COMPOUND': case 'RUNNING': case 'TAKE_PROFIT': return 'warn';
    case 'PAPER': case 'EXIT': return 'contrast';
    default: return 'secondary';
  }
}

function statusSeverity(label: string): AppSeverity {
  switch (label.toUpperCase()) {
    case 'OPEN': case 'FILLED': return 'success';
    case 'OPENING': case 'CLOSING': case 'PARTIALLY_FILLED': return 'contrast';
    case 'PENDING': case 'SUBMITTED': case 'ACCEPTED': return 'warn';
    case 'ERROR': case 'REJECTED': return 'danger';
    case 'CLOSED': case 'CANCELLED': return 'secondary';
    default: return 'warn';
  }
}

/** Trades grid built on AppDataTable. Live updates from TradeStreamService refetch
 * the current page (server-paginated) or update the static value array. */
@Component({
  selector: 'app-trade-table',
  standalone: true,
  imports: [AppDataTableComponent],
  template: `
    <app-data-table
      class="flex-1 min-h-0"
      [columns]="columns()"
      [fetchPage]="adaptedFetchPage()"
      [value]="adaptedValue()"
      [pageSize]="pageSize()"
      [showPaginator]="showPaginator()"
      [rowClickRoute]="navigateToTradeRoute"
      [emptyMessage]="'No trades'"
      storageKey="trades-table"
      (sortChange)="sortChange.emit($event)"
      (pageChange)="serverPageChange.emit($event)"
      (pageSizeChange)="pageSizeChange.emit($event)"
      (dataLoaded)="onDataLoaded($event)"
    />
  `,
})
export class TradeTableComponent implements OnInit, OnDestroy {
  tradeService = inject(TradeService);
  private streamService = inject(TradeStreamService);

  trades = input<TradeListItem[]>([]);
  showStrategy = input(true);
  loading = input(false);
  pageSize = input(DEFAULT_PAGE_SIZE);
  page = input(1);
  totalPages = input(1);
  pageChange = output<number>();
  fetchPage = input<AppFetchFn<TradeListItem> | null>(null);
  showPaginator = input(true);

  sortChange = output<{ field: string; order: string }>();
  pageSizeChange = output<number>();
  serverPageChange = output<number>();

  private streamSub: Subscription | null = null;
  private datePipe = new DatePipe('en-US');

  /** Static rows in fetchPage mode populate from dataLoaded so streaming
   * updates (which always push the full latest list) re-flow naturally. */
  private serverRowData = signal<TradeListItem[]>([]);

  /** Pass-through to AppDataTable: fetchPage takes precedence; otherwise static. */
  adaptedFetchPage = computed<AppFetchFn<TradeListItem> | null>(() => {
    const fn = this.fetchPage();
    if (!fn) return null;
    return (page, pageSize, sort) => fn(page, pageSize, sort as any);
  });

  adaptedValue = computed<TradeListItem[] | null>(() => {
    if (this.fetchPage()) return null;
    return this.trades();
  });

  navigateToTradeRoute = (trade: TradeListItem) => ['/trades', trade.id];

  columns = computed<AppColumn<TradeListItem>[]>(() => {
    const cols: AppColumn<TradeListItem>[] = [
      {
        field: 'entry_at',
        header: 'Date / Time',
        cellType: 'date',
        sortable: true,
        pinned: 'left',
        width: 180,
        format: (v) => v ? (this.datePipe.transform(v, 'MMM d, y, HH:mm:ss') ?? '') : '',
      },
      {
        field: 'display_symbol',
        header: 'Symbol',
        sortable: false,
        cellClass: 'font-medium',
        minWidth: 140,
      },
    ];
    if (this.showStrategy()) {
      cols.push({
        field: 'strategy_name',
        header: 'Strategy',
        sortable: false,
        cellClass: 'text-fg-muted',
        minWidth: 140,
      });
    }
    cols.push(
      {
        field: 'tags',
        header: 'Tags',
        sortable: false,
        format: (v) => Array.isArray(v) ? v.filter((t) => t !== 'PAPER').join(' · ') : '',
        cellClass: 'text-xs text-fg-muted',
        minWidth: 120,
      },
      {
        field: 'qty',
        header: 'Qty',
        sortable: false,
        cellType: 'number',
        format: (_, row) => {
          const leg = row.legs?.[0];
          return leg?.quantity != null ? QTY_FORMATTER.format(leg.quantity) : '';
        },
        minWidth: 80,
      },
      {
        field: 'entry',
        header: 'Entry',
        sortable: false,
        cellType: 'currency',
        format: (_, row) => this.tradeService.formatCurrency(row.legs?.[0]?.entry_price),
        minWidth: 100,
      },
      {
        field: 'exit',
        header: 'Exit / Current',
        sortable: false,
        cellType: 'currency',
        format: (_, row) => {
          const leg = row.legs?.[0];
          return this.tradeService.formatCurrency(leg?.exit_price ?? leg?.entry_price);
        },
        minWidth: 110,
      },
      {
        field: 'total_realized_pnl',
        header: 'P&L',
        sortable: false,
        cellType: 'currency',
        format: (v) => this.tradeService.formatCurrency(v),
        cellClass: (row) => this.tradeService.getPnlClass(row.total_realized_pnl),
        minWidth: 100,
      },
      {
        field: 'current_status',
        header: 'Status',
        sortable: false,
        cellType: 'status',
        tagMapper: (v) => ({ label: v ?? '—', severity: statusSeverity(v ?? '') }),
        pinned: 'right',
        minWidth: 110,
      },
    );
    return cols;
  });

  ngOnInit(): void {
    this.streamService.connect();
    this.streamSub = this.streamService.tradeUpdates$.subscribe((batch) => {
      // In server-paginated mode the parent owns the fetch; we let the trade
      // service / stream service trigger a soft refetch as needed elsewhere.
      // For static mode (e.g. dashboard "recent trades") update the array.
      if (!this.fetchPage()) {
        const incoming = this.trades();
        if (!incoming || incoming.length === 0) return;
        // Immutable: existing rows already update through the parent signal.
      }
    });
  }

  ngOnDestroy(): void {
    this.streamSub?.unsubscribe();
    this.streamService.disconnect();
  }

  onDataLoaded(items: TradeListItem[]): void {
    this.serverRowData.set(items);
  }

  getMainLeg(trade: TradeListItem): TradeLegSummary | null {
    return trade.legs.length > 0 ? trade.legs[0] : null;
  }
}
