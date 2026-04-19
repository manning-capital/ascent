import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, merge } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { DashboardStats } from '../models/dashboard.model';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private api = inject(ApiService);

  stats = signal<DashboardStats | null>(null);
  loading = signal(true);

  private loadStats$ = new Subject<void>();
  private refreshStats$ = new Subject<void>();

  constructor() {
    merge(
      this.loadStats$.pipe(tap(() => this.loading.set(true))),
      this.refreshStats$,
    )
      .pipe(
        switchMap(() =>
          this.api.get<DashboardStats>('/dashboard/stats').pipe(
            catchError(() => { this.loading.set(false); return EMPTY; })
          ),
        ),
      )
      .subscribe(stats => {
        this.stats.set(stats);
        this.loading.set(false);
      });
  }

  loadStats(): void {
    this.loadStats$.next();
  }

  refreshStats(): void {
    this.refreshStats$.next();
  }
}
