import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { TradeListItem, TradeDetail, PaginatedResponse } from '../models/trade.model';

const CURRENCY_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
});

@Injectable({ providedIn: 'root' })
export class TradeService {
  private api = inject(ApiService);

  trades = signal<TradeListItem[]>([]);
  totalTrades = signal(0);
  totalPages = signal(0);
  loading = signal(true);

  selectedTrade = signal<TradeDetail | null>(null);

  private loadTrades$ = new Subject<Record<string, any>>();
  private loadDetail$ = new Subject<string>();

  constructor() {
    this.loadTrades$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(params =>
        this.api.get<PaginatedResponse<TradeListItem>>('/trades', params).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.trades.set(res.items);
      this.totalTrades.set(res.total);
      this.totalPages.set(res.total_pages);
      this.loading.set(false);
    });

    this.loadDetail$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(tradeId =>
        this.api.get<TradeDetail>(`/trades/${tradeId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(trade => {
      this.selectedTrade.set(trade);
      this.loading.set(false);
    });
  }

  loadTrades(params: Record<string, any> = {}): void {
    this.loadTrades$.next(params);
  }

  loadTradeDetail(tradeId: string): void {
    this.loadDetail$.next(tradeId);
  }

  getPnlClass(value: number | null | undefined): string {
    if (value == null || value === 0) return 'text-surface-500';
    return value > 0 ? 'text-green-500' : 'text-red-500';
  }

  formatCurrency(value: number | null | undefined): string {
    if (value == null) return '—';
    return CURRENCY_FORMATTER.format(value);
  }

  formatPercent(pnl: number | null | undefined, entryPrice: number | null | undefined, quantity: number | null | undefined): string {
    if (pnl == null || entryPrice == null || quantity == null || entryPrice === 0 || quantity === 0) return '—';
    const percent = (pnl / (entryPrice * quantity)) * 100;
    return (percent >= 0 ? '+' : '') + percent.toFixed(2) + '%';
  }
}
