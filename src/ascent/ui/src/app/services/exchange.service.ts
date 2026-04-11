import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { ExchangeListItem, ExchangeStats } from '../models/exchange.model';
import { UniverseItem } from '../models/asset.model';
import { PaginatedResponse } from '../models/trade.model';

@Injectable({ providedIn: 'root' })
export class ExchangeService {
  private api = inject(ApiService);

  exchanges = signal<ExchangeListItem[]>([]);
  selectedExchange = signal<ExchangeListItem | null>(null);
  loading = signal(true);
  exchangeStats = signal<ExchangeStats | null>(null);
  statsLoading = signal(false);

  private loadExchanges$ = new Subject<void>();
  private loadDetail$ = new Subject<{ exchangeId: string; silent: boolean }>();
  private loadStats$ = new Subject<string>();

  constructor() {
    this.loadExchanges$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<PaginatedResponse<ExchangeListItem>>('/exchanges', { page_size: 10000 }).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.exchanges.set(res.items);
      this.loading.set(false);
    });

    this.loadDetail$.pipe(
      tap(({ silent }) => { if (!silent) this.loading.set(true); }),
      switchMap(({ exchangeId }) =>
        this.api.get<ExchangeListItem>(`/exchanges/${exchangeId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(exchange => {
      this.selectedExchange.set(exchange);
      this.loading.set(false);
    });

    this.loadStats$.pipe(
      tap(() => this.statsLoading.set(true)),
      switchMap(exchangeId =>
        this.api.get<ExchangeStats>(`/exchanges/${exchangeId}/stats`).pipe(
          catchError(() => { this.statsLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(stats => {
      this.exchangeStats.set(stats);
      this.statsLoading.set(false);
    });
  }

  loadExchanges(): void {
    this.loadExchanges$.next();
  }

  loadExchangesPaginated(page: number, pageSize: number, filters?: { search?: string; is_active?: boolean | null }, sort?: { field: string; order: string }): Observable<PaginatedResponse<ExchangeListItem>> {
    const params: Record<string, any> = { page, page_size: pageSize };
    if (filters?.search) params['search'] = filters.search;
    if (filters?.is_active != null) params['is_active'] = filters.is_active;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<ExchangeListItem>>('/exchanges', params);
  }

  loadExchangeDetail(exchangeId: string, silent = false): void {
    this.loadDetail$.next({ exchangeId, silent });
  }

  loadExchangeStats(exchangeId: string): void {
    this.loadStats$.next(exchangeId);
  }

  // Universe methods
  batchAddInstruments(exchangeId: string, instrumentIds: string[], startOrder: number): Observable<UniverseItem[]> {
    return this.api.post<UniverseItem[]>(`/exchanges/${exchangeId}/universe/batch`, { instrument_ids: instrumentIds, start_order: startOrder });
  }

  removeUniverseItem(exchangeId: string, instrumentId: string): Observable<any> {
    return this.api.delete(`/exchanges/${exchangeId}/universe/${instrumentId}`);
  }

  batchAddComposites(exchangeId: string, compositeIds: string[], startOrder: number): Observable<any[]> {
    return this.api.post<any[]>(`/exchanges/${exchangeId}/composite-universe/batch`, { composite_ids: compositeIds, start_order: startOrder });
  }

  removeCompositeUniverseItem(exchangeId: string, compositeId: string): Observable<any> {
    return this.api.delete(`/exchanges/${exchangeId}/composite-universe/${compositeId}`);
  }
}
