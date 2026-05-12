import { Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, EMPTY, of } from 'rxjs';
import { switchMap, tap, catchError, shareReplay } from 'rxjs/operators';
import { ApiService } from './api.service';
import { PaginatedResponse } from '../models/trade.model';
import { DataSourceInfo, DataExplorerFilterOptions, DataSeriesResponse } from '../models/data-explorer.model';

@Injectable({ providedIn: 'root' })
export class DataExplorerService {
  private api = inject(ApiService);

  dataSources = signal<DataSourceInfo[]>([]);
  filterOptions = signal<DataExplorerFilterOptions>({ entities: [], descriptors: [], periods: null });
  rows = signal<Record<string, any>[]>([]);
  totalRows = signal(0);
  totalPages = signal(0);
  loading = signal(false);
  filtersLoading = signal(false);

  private loadSources$ = new Subject<void>();
  private loadFilters$ = new Subject<string>();
  private loadData$ = new Subject<Record<string, any>>();

  constructor() {
    this.loadSources$.pipe(
      switchMap(() =>
        this.api.get<DataSourceInfo[]>('/data/sources').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(sources => this.dataSources.set(sources));

    this.loadFilters$.pipe(
      tap(() => this.filtersLoading.set(true)),
      switchMap(table =>
        this.api.get<DataExplorerFilterOptions>('/data/filters', { table }).pipe(
          catchError(() => { this.filtersLoading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(options => {
      this.filterOptions.set(options);
      this.filtersLoading.set(false);
    });

    this.loadData$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(params =>
        this.api.get<PaginatedResponse<Record<string, any>>>('/data/query', params).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(res => {
      this.rows.set(res.items);
      this.totalRows.set(res.total);
      this.totalPages.set(res.total_pages);
      this.loading.set(false);
    });
  }

  loadSources(): void {
    this.loadSources$.next();
  }

  loadFilterOptions(table: string): void {
    this.loadFilters$.next(table);
  }

  loadData(params: Record<string, any>): void {
    this.loadData$.next(params);
  }

  queryData(params: Record<string, any>): Observable<PaginatedResponse<Record<string, any>>> {
    return this.api.get<PaginatedResponse<Record<string, any>>>('/data/query', params);
  }

  // ─── Series fetch + cache ──────────────────────────────────────
  // The chart cells call fetchSeries() once per series; multiple cells
  // referencing the same (table, entity, descriptor, period, range, bucket)
  // tuple share a single in-flight observable via shareReplay so the network
  // request happens only once.
  private seriesCache = new Map<string, Observable<DataSeriesResponse>>();

  fetchSeries(params: {
    table: string;
    entityId: string;
    descriptorId: string;
    periodId?: string;
    start?: string | null;
    end?: string | null;
    bucket?: string;
    aggregation?: string;
  }): Observable<DataSeriesResponse> {
    const key = [
      params.table,
      params.entityId,
      params.descriptorId,
      params.periodId ?? '',
      params.start ?? '',
      params.end ?? '',
      params.bucket ?? 'none',
      params.aggregation ?? 'none',
    ].join('|');

    const cached = this.seriesCache.get(key);
    if (cached) return cached;

    const queryParams: Record<string, any> = {
      table: params.table,
      entity_id: params.entityId,
      descriptor_id: params.descriptorId,
    };
    if (params.periodId) queryParams['period_id'] = params.periodId;
    if (params.start) queryParams['start'] = params.start;
    if (params.end) queryParams['end'] = params.end;
    if (params.bucket && params.bucket !== 'none') queryParams['bucket'] = params.bucket;
    if (params.aggregation && params.aggregation !== 'none') queryParams['aggregation'] = params.aggregation;

    const obs = this.api
      .get<DataSeriesResponse>('/data/series', queryParams)
      .pipe(
        catchError(() => of<DataSeriesResponse>({ points: [], entity_label: '', descriptor_label: '' })),
        shareReplay(1),
      );
    this.seriesCache.set(key, obs);
    return obs;
  }

  /** Drop the series cache. Called when the workspace's table or time range
   *  changes — old cache entries are no longer relevant. */
  clearSeriesCache(): void {
    this.seriesCache.clear();
  }
}
