import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { DashboardStats } from '../models/dashboard.model';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private api = inject(ApiService);

  stats = signal<DashboardStats | null>(null);
  loading = signal(true);

  private loadStats$ = new Subject<void>();

  constructor() {
    this.loadStats$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<DashboardStats>('/dashboard/stats').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(stats => {
      this.stats.set(stats);
      this.loading.set(false);
    });
  }

  loadStats(): void {
    this.loadStats$.next();
  }
}
