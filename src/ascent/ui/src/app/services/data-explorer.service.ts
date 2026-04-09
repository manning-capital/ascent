import { Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, EMPTY } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { PaginatedResponse } from '../models/trade.model';
import { DataSourceInfo, DataExplorerFilterOptions } from '../models/data-explorer.model';

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
}
