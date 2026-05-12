import { Injectable, NgZone, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { ContextResponse } from '../models/context.model';

export interface ContextLoadOptions {
  start?: string | null;
  end?: string | null;
  series?: string[];
  tradeId?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ContextService {
  private api = inject(ApiService);
  private zone = inject(NgZone);

  /**
   * Load the reconstructed context for a strategy run. The response
   * mirrors the same `Context` shape persisted on `FeedRun.context`,
   * plus the resolved series ready to plot.
   */
  loadStrategyRunContext(
    strategyId: string,
    runId: string,
    opts: ContextLoadOptions = {},
  ): Observable<ContextResponse> {
    const params = this.buildParams(opts);
    return this.api.get<ContextResponse>(
      `/strategies/${strategyId}/runs/${runId}/context`,
      params,
    );
  }

  /**
   * Open an SSE stream of context updates for a strategy run. The server
   * emits the current snapshot immediately on connect, then a fresh
   * `ContextResponse` every time the strategy ticks. The EventSource
   * listener runs outside the Angular zone; updates are re-entered via
   * NgZone.run so signals trigger change detection.
   */
  streamStrategyRunContext(
    strategyId: string,
    runId: string,
    opts: ContextLoadOptions = {},
  ): Observable<ContextResponse> {
    const params = this.buildParams(opts);
    const query = new URLSearchParams(params).toString();
    const url =
      `/api/strategies/${strategyId}/runs/${runId}/context/stream` +
      (query ? `?${query}` : '');

    return new Observable<ContextResponse>(subscriber => {
      let source: EventSource | null = null;
      this.zone.runOutsideAngular(() => {
        source = new EventSource(url);
        source.addEventListener('context_update', (ev: MessageEvent) => {
          try {
            const parsed = JSON.parse(ev.data) as ContextResponse;
            this.zone.run(() => subscriber.next(parsed));
          } catch (err) {
            // Malformed payload — log and keep the connection open.
            console.error('Failed to parse context_update SSE payload', err);
          }
        });
        source.onerror = (ev) => {
          // Browsers auto-reconnect EventSource on errors. Surface the
          // event for debugging but don't tear the subscription down.
          console.warn('Context SSE error (will auto-reconnect)', ev);
        };
      });
      return () => {
        source?.close();
      };
    });
  }

  private buildParams(opts: ContextLoadOptions): Record<string, string> {
    const params: Record<string, string> = {};
    if (opts.start) params['start'] = opts.start;
    if (opts.end) params['end'] = opts.end;
    if (opts.series && opts.series.length > 0) {
      params['series'] = opts.series.join(',');
    }
    if (opts.tradeId) params['trade_id'] = opts.tradeId;
    return params;
  }
}
