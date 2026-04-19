import { Injectable, NgZone, inject } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { TradeListItem } from '../models/trade.model';

/**
 * Connects to the `/api/trades/stream` SSE endpoint and emits
 * real-time trade updates that AG Grid can apply as transactions.
 *
 * Updates are buffered over a short window and flushed as batches,
 * deduped by trade id (latest wins). The EventSource listener runs
 * outside the Angular zone; only the batched flush re-enters the zone.
 */
@Injectable({ providedIn: 'root' })
export class TradeStreamService {
  private zone = inject(NgZone);
  private eventSource: EventSource | null = null;
  private _tradeUpdates$ = new Subject<TradeListItem[]>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private buffer = new Map<string, TradeListItem>();

  private static readonly FLUSH_INTERVAL_MS = 300;

  /** Observable of batched real-time trade updates (deduped by id). */
  tradeUpdates$: Observable<TradeListItem[]> = this._tradeUpdates$.asObservable();

  connect(): void {
    if (this.eventSource) return;

    this.zone.runOutsideAngular(() => {
      this.eventSource = new EventSource('/api/trades/stream');

      this.eventSource.addEventListener('trade_update', (ev: MessageEvent) => {
        try {
          const trade: TradeListItem = JSON.parse(ev.data);
          this.buffer.set(trade.id, trade);
          if (this.flushTimer === null) {
            this.flushTimer = setTimeout(() => this.flush(), TradeStreamService.FLUSH_INTERVAL_MS);
          }
        } catch {
          // Ignore malformed events
        }
      });

      this.eventSource.onerror = () => {
        this.cleanup();
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      };
    });
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    this.buffer.clear();
    this.cleanup();
  }

  private flush(): void {
    this.flushTimer = null;
    if (this.buffer.size === 0) return;
    const batch = Array.from(this.buffer.values());
    this.buffer.clear();
    this.zone.run(() => this._tradeUpdates$.next(batch));
  }

  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
