import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { ExchangeListItem } from '../models/exchange.model';

@Injectable({ providedIn: 'root' })
export class ExchangeService {
  private api = inject(ApiService);

  exchanges = signal<ExchangeListItem[]>([]);
  selectedExchange = signal<ExchangeListItem | null>(null);
  loading = signal(true);

  private loadExchanges$ = new Subject<void>();
  private loadDetail$ = new Subject<{ exchangeId: string; silent: boolean }>();

  constructor() {
    this.loadExchanges$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<ExchangeListItem[]>('/exchanges').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(exchanges => {
      this.exchanges.set(exchanges);
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
  }

  loadExchanges(): void {
    this.loadExchanges$.next();
  }

  loadExchangeDetail(exchangeId: string, silent = false): void {
    this.loadDetail$.next({ exchangeId, silent });
  }
}
