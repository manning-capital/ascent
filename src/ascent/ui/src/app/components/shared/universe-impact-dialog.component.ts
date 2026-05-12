import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Dialog } from 'primeng/dialog';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { Skeleton } from 'primeng/skeleton';
import { ImpactReport } from '../../models/asset.model';

export type ImpactDialogChoice = 'remove' | 'disable' | 'cancel';

@Component({
  selector: 'app-universe-impact-dialog',
  standalone: true,
  imports: [Dialog, Button, Message, Skeleton],
  template: `
    <p-dialog
      [header]="'Remove ' + entityLabel"
      [(visible)]="visible"
      (visibleChange)="visibleChange.emit($event)"
      [modal]="true"
      [style]="{ width: '40rem' }"
      [closable]="true"
      [draggable]="false">
      <div class="flex flex-col gap-4">
        @if (impact) {
          @if (impact.can_remove) {
            <p-message severity="warn">
              Removing {{ entityName ?? 'this item' }} cannot be undone. No open trades or
              dependent items reference it.
            </p-message>
          } @else {
            <p-message severity="error">
              {{ entityName ?? 'This item' }} cannot be removed because of the following:
            </p-message>

            @if (impact.reasons.length > 0) {
              <ul class="list-disc list-inside text-sm text-surface-300 ml-2">
                @for (r of impact.reasons; track r) {
                  <li>{{ r }}</li>
                }
              </ul>
            }

            @if (impact.blocking_trades.length > 0) {
              <div>
                <p class="text-sm font-semibold mb-2">Open trades:</p>
                <div class="flex flex-col gap-1 text-sm max-h-48 overflow-auto">
                  @for (t of impact.blocking_trades; track t.trade_id) {
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-warning/5 border border-warning/10">
                      <span class="font-mono text-xs text-surface-400">{{ shortId(t.trade_id) }}</span>
                      <span class="text-xs text-surface-300">
                        {{ t.state }}{{ t.direction ? ' · ' + t.direction : '' }}{{ t.quantity != null ? ' · qty ' + t.quantity : '' }}
                      </span>
                    </div>
                  }
                </div>
              </div>
            }

            @if (impact.blocking_scope_items.length > 0) {
              <div>
                <p class="text-sm font-semibold mb-2">Dependent items:</p>
                <div class="flex flex-col gap-1 text-sm max-h-48 overflow-auto">
                  @for (s of impact.blocking_scope_items; track scopeKey(s)) {
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-negative/5 border border-negative/10">
                      <span class="text-xs text-surface-400">{{ scopeLabel(s) }}</span>
                      <span class="font-mono text-xs text-surface-500">{{ scopeIdLabel(s) }}</span>
                    </div>
                  }
                </div>
              </div>
            }

            @if (impact.suggested_action === 'disable' && supportsDisable) {
              <p-message severity="info">
                You can <strong>disable</strong> {{ entityName ?? 'this item' }} instead. New trades will be blocked,
                but existing open trades can still be managed and exited.
              </p-message>
            } @else if (impact.suggested_action === 'clear_blockers') {
              <p-message severity="info">
                Resolve the dependents above first, or wait for the open trades to close, then try again.
              </p-message>
            }
          }

          <div class="flex justify-end gap-2">
            <p-button (onClick)="choose('cancel')" severity="secondary" [outlined]="true" size="small" label="Cancel"/>
            @if (!impact.can_remove && impact.suggested_action === 'disable' && supportsDisable) {
              <p-button (onClick)="choose('disable')" severity="warn" size="small" label="Disable Instead" [loading]="busy"/>
            }
            <p-button
              (onClick)="choose('remove')"
              severity="danger"
              size="small"
              label="Remove"
              [disabled]="!impact.can_remove"
              [loading]="busy"/>
          </div>
        } @else {
          <div class="flex flex-col gap-2">
            <p-skeleton width="100%" height="1.5rem"/>
            <p-skeleton width="80%" height="1.5rem"/>
            <p-skeleton width="60%" height="1.5rem"/>
          </div>
        }
      </div>
    </p-dialog>
  `,
})
export class UniverseImpactDialogComponent {
  @Input() visible = false;
  @Input() entityLabel = 'Item';
  @Input() entityName: string | null = null;
  @Input() impact: ImpactReport | null = null;
  @Input() supportsDisable = true;
  @Input() busy = false;

  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() decision = new EventEmitter<ImpactDialogChoice>();

  choose(choice: ImpactDialogChoice): void {
    this.decision.emit(choice);
  }

  shortId(id: string | null): string {
    return id ? id.slice(0, 8) : '';
  }

  scopeKey(s: { strategy_id?: string | null; feed_id?: string | null; instrument_id?: string | null; composite_id?: string | null; scope_type: string }): string {
    return [s.scope_type, s.strategy_id, s.feed_id, s.instrument_id, s.composite_id]
      .map(v => v ?? '')
      .join('|');
  }

  scopeLabel(s: { scope_type: string; display_name: string | null }): string {
    const map: Record<string, string> = {
      strategy_universe: 'Strategy universe item',
      strategy_composite_universe: 'Strategy composite-universe item',
      feed_universe: 'Feed universe item',
      feed_composite_universe: 'Feed composite-universe item',
      strategy_exchange: 'Strategy-exchange link',
    };
    const label = map[s.scope_type] ?? s.scope_type;
    return s.display_name ? `${label} — ${s.display_name}` : label;
  }

  scopeIdLabel(s: { instrument_id: string | null; composite_id: string | null; strategy_id: string | null; exchange_id: string | null }): string {
    const id = s.instrument_id ?? s.composite_id ?? s.exchange_id ?? s.strategy_id;
    return this.shortId(id);
  }
}
