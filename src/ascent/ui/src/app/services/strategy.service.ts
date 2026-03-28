import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { StrategyListItem, StrategyDetail, StrategyStats } from '../models/strategy.model';
import { TradeListItem, PaginatedResponse } from '../models/trade.model';
import { OrderListItem } from '../models/order.model';
import { UniverseItem, UniverseItemCreate } from '../models/asset.model';

@Injectable({ providedIn: 'root' })
export class StrategyService {
  private api = inject(ApiService);

  strategies = signal<StrategyListItem[]>([]);
  selectedStrategy = signal<StrategyDetail | null>(null);
  strategyTrades = signal<TradeListItem[]>([]);
  strategyTradesTotalPages = signal(1);
  strategyTradesLoading = signal(false);
  strategyStats = signal<StrategyStats | null>(null);
  strategyOrders = signal<OrderListItem[]>([]);
  strategyOrdersTotalPages = signal(1);
  strategyOrdersLoading = signal(false);
  statsLoading = signal(false);
  loading = signal(true);
  saving = signal(false);

  private loadStrategies$ = new Subject<void>();
  private loadDetail$ = new Subject<{ strategyId: string; silent: boolean }>();
  private loadTrades$ = new Subject<{ strategyId: string; page: number; pageSize: number }>();
  private loadStats$ = new Subject<string>();
  private loadOrders$ = new Subject<{ strategyId: string; page: number; pageSize: number }>();

  constructor() {
    this.loadStrategies$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<StrategyListItem[]>('/strategies').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(strategies => {
      this.strategies.set(strategies);
      this.loading.set(false);
    });

    this.loadDetail$.pipe(
      tap(({ silent }) => { if (!silent) this.loading.set(true); }),
      switchMap(({ strategyId }) =>
        this.api.get<StrategyDetail>(`/strategies/${strategyId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(strategy => {
      this.selectedStrategy.set(strategy);
      this.loading.set(false);
    });

    this.loadTrades$.pipe(
      tap(() => this.strategyTradesLoading.set(true)),
      switchMap(({ strategyId, page, pageSize }) =>
        this.api.get<PaginatedResponse<TradeListItem>>(`/strategies/${strategyId}/trades`, { page, page_size: pageSize }).pipe(
          catchError(() => { this.strategyTradesLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.strategyTrades.set(res.items);
      this.strategyTradesTotalPages.set(res.total_pages);
      this.strategyTradesLoading.set(false);
    });

    this.loadOrders$.pipe(
      tap(() => this.strategyOrdersLoading.set(true)),
      switchMap(({ strategyId, page, pageSize }) =>
        this.api.get<PaginatedResponse<OrderListItem>>(`/strategies/${strategyId}/orders`, { page, page_size: pageSize }).pipe(
          catchError(() => { this.strategyOrdersLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.strategyOrders.set(res.items);
      this.strategyOrdersTotalPages.set(res.total_pages);
      this.strategyOrdersLoading.set(false);
    });

    this.loadStats$.pipe(
      tap(() => this.statsLoading.set(true)),
      switchMap(strategyId =>
        this.api.get<StrategyStats>(`/strategies/${strategyId}/stats`).pipe(
          catchError(() => { this.statsLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(stats => {
      this.strategyStats.set(stats);
      this.statsLoading.set(false);
    });
  }

  loadStrategies(): void {
    this.loadStrategies$.next();
  }

  loadStrategyDetail(strategyId: string, silent = false): void {
    this.loadDetail$.next({ strategyId, silent });
  }

  loadStrategyTrades(strategyId: string, page: number = 1, pageSize: number = 10): void {
    this.loadTrades$.next({ strategyId, page, pageSize });
  }

  loadStrategyStats(strategyId: string): void {
    this.loadStats$.next(strategyId);
  }

  loadStrategyOrders(strategyId: string, page: number = 1, pageSize: number = 10): void {
    this.loadOrders$.next({ strategyId, page, pageSize });
  }

  updateStrategy(strategyId: string, data: Record<string, any>): Observable<any> {
    return this.api.put(`/strategies/${strategyId}`, data);
  }

  loadUniverse(strategyId: string): Observable<UniverseItem[]> {
    return this.api.get<UniverseItem[]>(`/strategies/${strategyId}/universe`);
  }

  addUniverseItem(strategyId: string, data: UniverseItemCreate): Observable<any> {
    return this.api.post(`/strategies/${strategyId}/universe`, data);
  }

  removeUniverseItem(strategyId: string, providerId: string, fromAssetId: string, toAssetId: string): Observable<any> {
    return this.api.delete(`/strategies/${strategyId}/universe/${providerId}/${fromAssetId}/${toAssetId}`);
  }
}
