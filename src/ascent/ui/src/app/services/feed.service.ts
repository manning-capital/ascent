import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { FeedListItem, FeedDetail, FeedRunListItem, FeedPartitionItem, PartitionDataResponse, StrategyFeedDAG, StrategyRunListItem } from '../models/feed.model';
import { PaginatedResponse } from '../models/trade.model';
import { UniverseItem, UniverseItemCreate } from '../models/asset.model';
import { RunFilter } from '../components/shared/run-viewer.component';

@Injectable({ providedIn: 'root' })
export class FeedService {
  private api = inject(ApiService);

  feeds = signal<FeedListItem[]>([]);
  selectedFeed = signal<FeedDetail | null>(null);
  loading = signal(false);
  saving = signal(false);

  private loadFeeds$ = new Subject<void>();
  private loadDetail$ = new Subject<{ feedId: string; silent: boolean }>();

  constructor() {
    this.loadFeeds$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<FeedListItem[]>('/feeds').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(feeds => {
      this.feeds.set(feeds);
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

  loadFeedDetail(feedId: string, silent = false): void {
    this.loadDetail$.next({ feedId, silent });
  }

  loadFeedRuns(feedId: string, page: number = 1, pageSize: number = 20, filter?: RunFilter): Observable<PaginatedResponse<FeedRunListItem>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filter?.started_after) params['started_after'] = filter.started_after;
    if (filter?.started_before) params['started_before'] = filter.started_before;
    return this.api.get<PaginatedResponse<FeedRunListItem>>(`/feeds/${feedId}/runs`, params);
  }

  loadPartitions(feedId: string, page: number = 1, pageSize: number = 50, start?: string, end?: string, status?: string): Observable<PaginatedResponse<FeedPartitionItem>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (start) params['start'] = start;
    if (end) params['end'] = end;
    if (status) params['status'] = status;
    return this.api.get<PaginatedResponse<FeedPartitionItem>>(`/feeds/${feedId}/partitions`, params);
  }

  loadPartitionData(feedId: string, partitionId: string, page: number = 1, pageSize: number = 50): Observable<PartitionDataResponse> {
    return this.api.get<PartitionDataResponse>(`/feeds/${feedId}/partitions/${partitionId}/data`, { page, page_size: pageSize });
  }

  loadStrategyFeedDAG(strategyId: string) {
    return this.api.get<StrategyFeedDAG>(`/strategies/${strategyId}/feeds`);
  }

  loadStrategyRuns(strategyId: string, page: number = 1, pageSize: number = 20, filter?: RunFilter): Observable<PaginatedResponse<StrategyRunListItem>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filter?.started_after) params['started_after'] = filter.started_after;
    if (filter?.started_before) params['started_before'] = filter.started_before;
    return this.api.get<PaginatedResponse<StrategyRunListItem>>(`/strategies/${strategyId}/runs`, params);
  }

  loadFeedUniverse(feedId: string): Observable<UniverseItem[]> {
    return this.api.get<UniverseItem[]>(`/feeds/${feedId}/universe`);
  }

  addFeedUniverseItem(feedId: string, data: UniverseItemCreate): Observable<any> {
    return this.api.post(`/feeds/${feedId}/universe`, data);
  }

  removeFeedUniverseItem(feedId: string, providerId: string, fromAssetId: string, toAssetId: string): Observable<any> {
    return this.api.delete(`/feeds/${feedId}/universe/${providerId}/${fromAssetId}/${toAssetId}`);
  }
}
