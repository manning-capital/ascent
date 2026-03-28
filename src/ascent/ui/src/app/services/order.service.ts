import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { OrderListItem } from '../models/order.model';

@Injectable({ providedIn: 'root' })
export class OrderService {
  private api = inject(ApiService);

  orders = signal<OrderListItem[]>([]);
  loading = signal(false);

  private load$ = new Subject<void>();

  constructor() {
    this.load$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<OrderListItem[]>('/orders').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(items => {
      this.orders.set(items);
      this.loading.set(false);
    });
  }

  loadOrders(): void {
    this.load$.next();
  }
}
