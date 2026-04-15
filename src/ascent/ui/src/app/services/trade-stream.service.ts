import { Injectable, NgZone, inject } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { TradeListItem } from '../models/trade.model';

/**
 * Connects to the `/api/trades/stream` SSE endpoint and emits
 * real-time trade updates that AG Grid can apply as transactions.
 *
 * Usage:
 *   stream.connect();            // start listening
 *   stream.tradeUpdate$          // Observable<TradeListItem>
 *   stream.disconnect();         // stop listening
 *
 * Auto-reconnects after 3 seconds if the connection drops.
 */
@Injectable({ providedIn: 'root' })
export class TradeStreamService {
  private zone = inject(NgZone);
  private eventSource: EventSource | null = null;
  private _tradeUpdate$ = new Subject<TradeListItem>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  /** Observable of real-time trade updates. */
  tradeUpdate$: Observable<TradeListItem> = this._tradeUpdate$.asObservable();

  connect(): void {
    if (this.eventSource) return;

    this.eventSource = new EventSource('/api/trades/stream');

    this.eventSource.addEventListener('trade_update', (ev: MessageEvent) => {
      try {
        const trade: TradeListItem = JSON.parse(ev.data);
        // Run inside Angular zone so change detection picks it up
        this.zone.run(() => this._tradeUpdate$.next(trade));
      } catch {
        // Ignore malformed events
      }
    });

    this.eventSource.onerror = () => {
      this.cleanup();
      // Auto-reconnect after 3s
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.cleanup();
  }

  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
