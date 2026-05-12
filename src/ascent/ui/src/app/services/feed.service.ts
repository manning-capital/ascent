import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { FeedListItem, FeedDetail, FeedRunDetail, FeedRunListItem, FeedRunTradeItem, FeedRunLineageResponse, FeedRunUniverseCompositeItem, FeedRunUniverseInstrumentItem, RunDataResponse, StrategyFeedDAG, StrategyRunListItem, TradeFeedRunItem } from '../models/feed.model';
import { PaginatedResponse } from '../models/trade.model';
import { ImpactReport, UniverseItem, UniverseItemCreate } from '../models/asset.model';
import { RunFilter } from '../components/shared/run-viewer.component';

@Injectable({ providedIn: 'root' })
export class FeedService {
  private api = inject(ApiService);

  feeds = signal<FeedListItem[]>([]);
  selectedFeed = signal<FeedDetail | null>(null);
  loading = signal(true);
  saving = signal(false);

  private loadFeeds$ = new Subject<void>();
  private loadDetail$ = new Subject<{ feedId: string; silent: boolean }>();

  constructor() {
    this.loadFeeds$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<PaginatedResponse<FeedListItem>>('/feeds', { page_size: 10000 }).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.feeds.set(res.items);
      this.loading.set(false);
    });

    this.loadDetail$.pipe(
      tap(({ silent }) => { if (!silent) this.loading.set(true); }),
      switchMap(({ feedId }) =>
        this.api.get<FeedDetail>(`/feeds/${feedId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(feed => {
      this.selectedFeed.set(feed);
      this.loading.set(false);
    });
  }

  loadFeeds(): void {
    this.loadFeeds$.next();
  }

  loadFeedsPaginated(page: number, pageSize: number, filters?: { search?: string; is_active?: boolean | null }, sort?: { field: string; order: string }): Observable<PaginatedResponse<FeedListItem>> {
    const params: Record<string, any> = { page, page_size: pageSize };
    if (filters?.search) params['search'] = filters.search;
    if (filters?.is_active != null) params['is_active'] = filters.is_active;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<FeedListItem>>('/feeds', params);
  }

  loadFeedDetail(feedId: string, silent = false): void {
    this.loadDetail$.next({ feedId, silent });
  }

  loadFeedRuns(feedId: string, page: number = 1, pageSize: number = 20, filter?: RunFilter, sort?: { field: string; order: string }): Observable<PaginatedResponse<FeedRunListItem>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filter?.started_after) params['started_after'] = filter.started_after;
    if (filter?.started_before) params['started_before'] = filter.started_before;
    if (filter?.status) params['status'] = filter.status;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<FeedRunListItem>>(`/feeds/${feedId}/runs`, params);
  }

  loadRunData(feedId: string, runId: string, page: number = 1, pageSize: number = 50): Observable<RunDataResponse> {
    return this.api.get<RunDataResponse>(`/feeds/${feedId}/runs/${runId}/data`, { page, page_size: pageSize });
  }

  loadRunTrades(feedId: string, runId: string): Observable<FeedRunTradeItem[]> {
    return this.api.get<FeedRunTradeItem[]>(`/feeds/${feedId}/runs/${runId}/trades`);
  }

  loadFeedRunUniverseInstruments(feedId: string, runId: string, page: number = 1, pageSize: number = 50): Observable<PaginatedResponse<FeedRunUniverseInstrumentItem>> {
    return this.api.get<PaginatedResponse<FeedRunUniverseInstrumentItem>>(
      `/feeds/${feedId}/runs/${runId}/universe/instruments`,
      { page, page_size: pageSize },
    );
  }

  loadFeedRunUniverseComposites(feedId: string, runId: string, page: number = 1, pageSize: number = 50): Observable<PaginatedResponse<FeedRunUniverseCompositeItem>> {
    return this.api.get<PaginatedResponse<FeedRunUniverseCompositeItem>>(
      `/feeds/${feedId}/runs/${runId}/universe/composites`,
      { page, page_size: pageSize },
    );
  }

  loadFeedRunLineage(feedId: string, runId: string): Observable<FeedRunLineageResponse> {
    return this.api.get<FeedRunLineageResponse>(`/feeds/${feedId}/runs/${runId}/lineage`);
  }

  loadTradeFeedRuns(tradeId: string): Observable<TradeFeedRunItem[]> {
    return this.api.get<TradeFeedRunItem[]>(`/trades/${tradeId}/feed-runs`);
  }

  loadStrategyFeedDAG(strategyId: string) {
    return this.api.get<StrategyFeedDAG>(`/strategies/${strategyId}/feeds`);
  }

  getStrategyRun(strategyId: string, runId: string): Observable<StrategyRunListItem> {
    return this.api.get<StrategyRunListItem>(`/strategies/${strategyId}/runs/${runId}`);
  }

  getFeedRun(feedId: string, runId: string): Observable<FeedRunDetail> {
    return this.api.get<FeedRunDetail>(`/feeds/${feedId}/runs/${runId}`);
  }

  loadStrategyRuns(strategyId: string, page: number = 1, pageSize: number = 20, filter?: RunFilter, sort?: { field: string; order: string }): Observable<PaginatedResponse<StrategyRunListItem>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filter?.started_after) params['started_after'] = filter.started_after;
    if (filter?.started_before) params['started_before'] = filter.started_before;
    if (filter?.status) params['status'] = filter.status;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<StrategyRunListItem>>(`/strategies/${strategyId}/runs`, params);
  }

  loadFeedUniverse(feedId: string): Observable<UniverseItem[]> {
    return this.api.get<UniverseItem[]>(`/feeds/${feedId}/universe`);
  }

  addFeedUniverseItem(feedId: string, data: UniverseItemCreate): Observable<any> {
    return this.api.post(`/feeds/${feedId}/universe`, data);
  }

  batchAddFeedInstruments(feedId: string, instrumentIds: string[], startOrder: number): Observable<UniverseItem[]> {
    return this.api.post<UniverseItem[]>(`/feeds/${feedId}/universe/batch`, { instrument_ids: instrumentIds, start_order: startOrder });
  }

  removeFeedUniverseItem(feedId: string, instrumentId: string): Observable<any> {
    return this.api.delete(`/feeds/${feedId}/universe/${instrumentId}`);
  }

  getFeedUniverseImpact(feedId: string, instrumentId: string): Observable<ImpactReport> {
    return this.api.get<ImpactReport>(`/feeds/${feedId}/universe/${instrumentId}/impact`);
  }

  setFeedUniverseItemActive(feedId: string, instrumentId: string, isActive: boolean): Observable<UniverseItem> {
    return this.api.patch<UniverseItem>(`/feeds/${feedId}/universe/${instrumentId}`, { is_active: isActive });
  }

  // Composite universe
  loadFeedCompositeUniverse(feedId: string): Observable<any[]> {
    return this.api.get<any[]>(`/feeds/${feedId}/composite-universe`);
  }

  batchAddFeedComposites(feedId: string, compositeIds: string[], startOrder: number): Observable<any[]> {
    return this.api.post<any[]>(`/feeds/${feedId}/composite-universe/batch`, { composite_ids: compositeIds, start_order: startOrder });
  }

  removeFeedCompositeUniverseItem(feedId: string, compositeId: string): Observable<any> {
    return this.api.delete(`/feeds/${feedId}/composite-universe/${compositeId}`);
  }

  getFeedCompositeUniverseImpact(feedId: string, compositeId: string): Observable<ImpactReport> {
    return this.api.get<ImpactReport>(`/feeds/${feedId}/composite-universe/${compositeId}/impact`);
  }

  setFeedCompositeUniverseItemActive(feedId: string, compositeId: string, isActive: boolean): Observable<any> {
    return this.api.patch(`/feeds/${feedId}/composite-universe/${compositeId}`, { is_active: isActive });
  }
}
