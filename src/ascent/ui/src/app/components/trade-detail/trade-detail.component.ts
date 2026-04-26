import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { FeedService } from '../../services/feed.service';
import { TradeService } from '../../services/trade.service';
import { TradeStreamService } from '../../services/trade-stream.service';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';
import { DatePipe, JsonPipe } from '@angular/common';
import { Skeleton } from 'primeng/skeleton';
import { formatCloseReason } from '../shared/close-reason.util';
import { TradeFeedRunItem } from '../../models/feed.model';
import type { OrderDetail } from '../../models/order.model';
import { RunContextChartComponent } from './run-context-chart/run-context-chart.component';

const directionSeverity: Record<string, string> = {
  LONG: 'success',
  SHORT: 'danger',
};

const sideSeverity: Record<string, string> = {
  BUY: 'success',
  SELL: 'danger',
};

const orderStatusSeverity: Record<string, string> = {
  FILLED: 'success',
  PARTIALLY_FILLED: 'warn',
  CANCELLED: 'secondary',
  REJECTED: 'danger',
  PENDING: 'info',
  NEW: 'info',
};

type OrderRow = OrderDetail & { instrument_name: string };

@Component({
  selector: 'app-trade-detail',
  standalone: true,
  imports: [RouterLink, BadgeComponent, StatCardComponent, DatePipe, JsonPipe, Card, Tag, Skeleton, DataTableComponent, RunContextChartComponent],
  templateUrl: './trade-detail.component.html',
})
export class TradeDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  tradeService = inject(TradeService);
  private feedService = inject(FeedService);
  private streamService = inject(TradeStreamService);

  String = String;
  formatCloseReason = formatCloseReason;

  private tradeId: string | null = null;
  private streamSub: Subscription | null = null;

  sourceFeedRuns = signal<TradeFeedRunItem[]>([]);
  sourceFeedRunsLoading = signal(false);

  allOrders = computed<OrderRow[]>(() => {
    const trade = this.tradeService.selectedTrade();
    if (!trade) return [];
    const rows: OrderRow[] = [];
    for (const leg of trade.legs) {
      for (const order of leg.orders ?? []) {
        rows.push({ ...order, instrument_name: leg.instrument_name });
      }
    }
    rows.sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? ''));
    return rows;
  });

  legColumns: DataTableColumn[] = [
    { field: 'instrument_name', header: 'Instrument' },
    {
      field: 'direction',
      header: 'Direction',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: directionSeverity[v] ?? 'secondary',
      }),
    },
    { field: 'quantity', header: 'Quantity' },
    {
      field: 'entry_price',
      header: 'Entry Price',
      cellType: 'currency',
    },
    {
      field: 'exit_price',
      header: 'Exit Price',
      cellType: 'currency',
    },
    {
      field: 'realized_pnl',
      header: 'P&L',
      cellType: 'currency',
    },
  ];

  orderColumns: DataTableColumn[] = [
    { field: 'timestamp', header: 'Time', cellType: 'date', minWidth: 180 },
    { field: 'instrument_name', header: 'Instrument', minWidth: 140 },
    {
      field: 'side',
      header: 'Side',
      cellType: 'tag',
      minWidth: 80,
      tagMapper: (v: string) => ({
        label: v,
        severity: sideSeverity[v] ?? 'secondary',
      }),
    },
    { field: 'order_type', header: 'Type', minWidth: 90 },
    { field: 'quantity', header: 'Qty', minWidth: 90 },
    { field: 'price', header: 'Price', cellType: 'currency', minWidth: 110 },
    {
      field: 'filled_quantity',
      header: 'Filled',
      minWidth: 110,
      valueGetter: (params: any) => {
        const d = params.data;
        if (d?.filled_quantity !== null && d?.filled_quantity !== undefined) {
          return `${d.filled_quantity} / ${d.quantity}`;
        }
        return '--';
      },
    },
    { field: 'average_fill_price', header: 'Avg Fill', cellType: 'currency', minWidth: 110 },
    {
      field: 'current_status',
      header: 'Status',
      cellType: 'tag',
      minWidth: 140,
      tagMapper: (v: string) => ({
        label: v,
        severity: orderStatusSeverity[v] ?? 'secondary',
      }),
    },
  ];

  snapshotColumns: DataTableColumn[] = [
    {
      field: 'snapshot_type',
      header: 'Type',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: 'secondary',
      }),
    },
    { field: 'attribute_name', header: 'Attribute' },
    { field: 'attribute_value', header: 'Value', cellType: 'monospace' },
    { field: 'timestamp', header: 'Timestamp', cellType: 'date' },
  ];

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'secondary';
    }
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const tradeId = params.get('tradeId')!;
      this.tradeId = tradeId;
      this.tradeService.loadTradeDetail(tradeId);
      this.loadSourceFeedRuns(tradeId);
    });

    this.streamService.connect();
    this.streamSub = this.streamService.tradeUpdates$.subscribe(batch => {
      if (!this.tradeId) return;
      if (batch.some(item => item.id === this.tradeId)) {
        this.tradeService.refreshTradeDetail(this.tradeId);
      }
    });
  }

  ngOnDestroy(): void {
    this.streamSub?.unsubscribe();
    this.streamSub = null;
  }

  private loadSourceFeedRuns(tradeId: string): void {
    this.sourceFeedRuns.set([]);
    this.sourceFeedRunsLoading.set(true);
    this.feedService.loadTradeFeedRuns(tradeId).subscribe({
      next: runs => {
        this.sourceFeedRuns.set(runs);
        this.sourceFeedRunsLoading.set(false);
      },
      error: () => this.sourceFeedRunsLoading.set(false),
    });
  }
}
