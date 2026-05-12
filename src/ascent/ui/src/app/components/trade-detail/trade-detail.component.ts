import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { FeedService } from '../../services/feed.service';
import { TradeService } from '../../services/trade.service';
import { TradeStreamService } from '../../services/trade-stream.service';
import { BadgeComponent } from '../shared/badge.component';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import type { AppColumn, AppSeverity } from '../ui/data-table/app-column.model';
import { DatePipe, NgClass } from '@angular/common';
import { Skeleton } from 'primeng/skeleton';
import { formatCloseReason } from '../shared/close-reason.util';
import { TradeFeedRunItem } from '../../models/feed.model';
import type { OrderDetail } from '../../models/order.model';
import type { TradeStatus } from '../../models/trade.model';
import { RunContextChartComponent } from './run-context-chart/run-context-chart.component';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';

const directionSeverity: Record<string, AppSeverity> = {
  LONG: 'success',
  SHORT: 'danger',
};

const sideSeverity: Record<string, AppSeverity> = {
  BUY: 'success',
  SELL: 'danger',
};

const orderStatusSeverity: Record<string, AppSeverity> = {
  FILLED: 'success',
  PARTIALLY_FILLED: 'warn',
  CANCELLED: 'secondary',
  REJECTED: 'danger',
  PENDING: 'info',
  NEW: 'info',
};

type OrderRow = OrderDetail & { instrument_name: string };

interface LifecycleStep {
  status: string;
  timestamp: string | null;
  reached: boolean;
  current: boolean;
  kind: 'normal' | 'error';
  /** When true, the connector LEADING OUT of this step (to the next step)
   *  is rendered dashed — showing the trade jumped past the next happy-path
   *  stage on its way to a terminal off-path status. */
  jumpedNext?: boolean;
  /** When true, this step is one the trade SKIPPED OVER on an off-path
   *  exit. The dot itself is rendered dashed to match the dashed connector
   *  going through this region. */
  skipped?: boolean;
}

const TABS = ['Orders', 'Source'] as const;
type TabName = (typeof TABS)[number];

@Component({
  selector: 'app-trade-detail',
  standalone: true,
  imports: [
    RouterLink,
    BadgeComponent,
    DatePipe,
    NgClass,
    Card,
    Tag,
    Skeleton,
    Tabs,
    TabList,
    Tab,
    AppDataTableComponent,
    RunContextChartComponent,
    AppPageHeaderComponent,
  ],
  templateUrl: './trade-detail.component.html',
})
export class TradeDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  tradeService = inject(TradeService);
  private feedService = inject(FeedService);
  private streamService = inject(TradeStreamService);

  String = String;
  formatCloseReason = formatCloseReason;

  private tradeId: string | null = null;
  private streamSub: Subscription | null = null;

  activeTab = signal<TabName>('Orders');
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

  /** Most-recent-first list of status updates (used as fallback / overflow). */
  reversedStatuses = computed<TradeStatus[]>(() => {
    const trade = this.tradeService.selectedTrade();
    if (!trade) return [];
    return [...trade.statuses].slice().reverse();
  });

  /** Lifecycle steps for the horizontal stepper. Always returns exactly 5
   *  slots so dot positions are identical across every trade.
   *
   *  Layout:
   *   - Slots 0-3: PENDING / OPENING / OPEN / CLOSING (always)
   *   - Slot 4:    CLOSED for clean exits, or the terminal off-path status
   *                (CANCELLED / ERROR / REJECTED / FAILED) when the trade
   *                ended unhealthy — keeps the terminal indicator anchored
   *                at the far right regardless of outcome.
   *   - Connectors leading out of any slot past the last reached happy-path
   *     step are dashed, so the user can see exactly where the trade
   *     "jumped" off-path on its way to the terminal status. */
  lifecycleSteps = computed<LifecycleStep[]>(() => {
    const trade = this.tradeService.selectedTrade();
    if (!trade) return [];

    const happyPath = ['PENDING', 'OPENING', 'OPEN', 'CLOSING', 'CLOSED'];
    const errorish = new Set(['CANCELLED', 'ERROR', 'REJECTED', 'FAILED']);

    // First-seen timestamp for each status — sort by timestamp ascending so
    // the earliest entry wins when the same status appears twice.
    const firstSeen = new Map<string, string>();
    const sorted = [...trade.statuses].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    for (const s of sorted) {
      if (!firstSeen.has(s.status)) firstSeen.set(s.status, s.timestamp);
    }

    const latest = sorted.length > 0 ? sorted[sorted.length - 1].status : null;
    const latestTs = sorted.length > 0 ? sorted[sorted.length - 1].timestamp : null;
    const onErrorPath = latest != null && errorish.has(latest);

    // Index of the last happy-path slot the trade actually reached.
    let lastHappyReachedIdx = -1;
    for (let i = happyPath.length - 1; i >= 0; i--) {
      if (firstSeen.has(happyPath[i])) {
        lastHappyReachedIdx = i;
        break;
      }
    }

    return happyPath.map((status, idx) => {
      // Slot 4 is the terminal slot — replaced with the off-path status
      // when the trade went unhealthy. Anchored at the far right.
      if (idx === happyPath.length - 1 && onErrorPath && latest != null) {
        return {
          status: latest,
          timestamp: latestTs,
          reached: true,
          current: true,
          kind: 'error',
          jumpedNext: false,
        };
      }

      const ts = firstSeen.get(status) ?? null;
      const reached = ts != null;

      // Connector OUT of this slot is dashed if the trade jumped past the
      // next stage on its way to the terminal off-path status.
      const jumpedNext = onErrorPath && idx >= lastHappyReachedIdx && idx < happyPath.length - 1;
      // The slot itself is "skipped" when it's an unreached intermediate
      // happy-path step on an off-path trade — i.e., we jumped over it.
      const skipped = onErrorPath && !reached && idx > lastHappyReachedIdx;

      return {
        status,
        timestamp: ts,
        reached,
        current: !onErrorPath && reached && status === latest,
        kind: 'normal',
        jumpedNext,
        skipped,
      };
    });
  });

  legColumns: AppColumn[] = [
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

  orderColumns: AppColumn[] = [
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
      format: (_, row) => {
        if (row?.filled_quantity !== null && row?.filled_quantity !== undefined) {
          return `${row.filled_quantity} / ${row.quantity}`;
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

  snapshotColumns: AppColumn[] = [
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

  /** Class set for a lifecycle stepper dot. Returned as a single object so
   *  every class is applied exactly once — earlier we had multiple
   *  ``[class.bg-surface]`` bindings on the same element which caused only
   *  the last one to win and the connector line to show through the hollow
   *  current-state dot. */
  dotClasses(step: LifecycleStep): Record<string, boolean> {
    const isCurrentNormal = step.current && step.kind === 'normal';
    const isPastNormal = step.reached && step.kind === 'normal' && !step.current;
    const isFuture = !step.reached && step.kind === 'normal';
    const isError = step.kind === 'error';
    return {
      // Borders
      'border-primary': step.reached && step.kind === 'normal',
      'border-edge': isFuture,
      'border-negative': isError,
      // Fills — bg-surface (matches the stepper card background) on the
      // hollow states so the connector line behind the dot is masked.
      'bg-primary': isPastNormal,
      'bg-surface': isCurrentNormal || isFuture,
      'bg-negative': isError,
      // Outer ring on the active step
      'ring-2': step.current,
      'ring-primary': isCurrentNormal,
      'ring-negative': step.current && isError,
    };
  }

  onTabChange(tab: string): void {
    if (!TABS.includes(tab as TabName)) return;
    this.activeTab.set(tab as TabName);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const tradeId = params.get('tradeId')!;
      this.tradeId = tradeId;
      this.tradeService.loadTradeDetail(tradeId);
      this.loadSourceFeedRuns(tradeId);
    });

    this.route.queryParamMap.subscribe(qp => {
      const tab = qp.get('tab');
      if (tab && (TABS as readonly string[]).includes(tab)) {
        this.activeTab.set(tab as TabName);
      }
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
