import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { StrategyListItem, StrategyDetail } from '../models/strategy.model';
import { TradeListItem, PaginatedResponse } from '../models/trade.model';
import { UniverseItem, UniverseItemCreate } from '../models/asset.model';

@Injectable({ providedIn: 'root' })
export class StrategyService {
  private api = inject(ApiService);

  strategies = signal<StrategyListItem[]>([]);
  selectedStrategy = signal<StrategyDetail | null>(null);
  strategyTrades = signal<TradeListItem[]>([]);
  allStrategyTrades = signal<TradeListItem[]>([]);
  allTradesLoading = signal(false);
  loading = signal(false);
  saving = signal(false);

  private loadStrategies$ = new Subject<void>();
  private loadDetail$ = new Subject<{ strategyId: string; silent: boolean }>();
  private loadTrades$ = new Subject<{ strategyId: string; page: number; pageSize: number }>();
  private loadAllTrades$ = new Subject<string>();

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
      switchMap(({ strategyId, page, pageSize }) =>
        this.api.get<PaginatedResponse<TradeListItem>>(`/strategies/${strategyId}/trades`, { page, page_size: pageSize }).pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(res => {
      this.strategyTrades.set(res.items);
    });

    this.loadAllTrades$.pipe(
      tap(() => this.allTradesLoading.set(true)),
      switchMap(strategyId =>
        this.api.get<PaginatedResponse<TradeListItem>>(`/strategies/${strategyId}/trades`, { page: 1, page_size: 10000 }).pipe(
          catchError(() => { this.allTradesLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.allStrategyTrades.set(res.items);
      this.allTradesLoading.set(false);
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

  loadAllStrategyTrades(strategyId: string): void {
    this.loadAllTrades$.next(strategyId);
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
