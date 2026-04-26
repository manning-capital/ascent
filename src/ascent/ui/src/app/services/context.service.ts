import { Injectable, inject } from '@angular/core';
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
    const params: Record<string, string> = {};
    if (opts.start) params['start'] = opts.start;
    if (opts.end) params['end'] = opts.end;
    if (opts.series && opts.series.length > 0) {
      params['series'] = opts.series.join(',');
    }
    if (opts.tradeId) params['trade_id'] = opts.tradeId;
    return this.api.get<ContextResponse>(
      `/strategies/${strategyId}/runs/${runId}/context`,
      params,
    );
  }
}
