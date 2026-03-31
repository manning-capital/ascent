import { Component, computed, inject, input, Output, EventEmitter } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Button } from 'primeng/button';
import { EmptyStateComponent } from './empty-state.component';
import { AssetPairBadgeComponent, AssetPair } from './asset-pair-badge.component';
import { UniverseItem, Instrument } from '../../models/asset.model';
import { AssetService } from '../../services/asset.service';

/** A row representing one instrument in the universe. */
interface UniverseRow {
  instrumentId: string;
  instrumentName: string;
  instrumentDisplayName: string;
  instrumentTypeId: string;
  isActive: boolean;
  pair: AssetPair | null;
  order: number;
}

@Component({
  selector: 'app-universe-table',
  standalone: true,
  imports: [RouterLink, TableModule, Tag, Button, EmptyStateComponent, AssetPairBadgeComponent],
  styles: [`
    :host ::ng-deep .p-datatable {
      border-radius: 0.5rem;
      overflow: hidden;
    }
  `],
  template: `
    <p-table [value]="rows()" [paginator]="true" [rows]="pageSize" [showCurrentPageReport]="true"
             currentPageReportTemplate="{first}–{last} of {totalRecords}" [rowsPerPageOptions]="[5, 10, 25]">
      <ng-template #header>
        <tr>
          <th>Instrument</th>
          <th>Pair</th>
          <th>Instrument Type</th>
          <th class="w-24">Status</th>
          <th class="w-20"></th>
        </tr>
      </ng-template>
      <ng-template #body let-row>
        <tr>
          <td>
            <a [routerLink]="['/settings/instruments', row.instrumentId]" class="text-primary hover:underline font-medium">{{ row.instrumentDisplayName || row.instrumentName }}</a>
            @if (row.instrumentDisplayName && row.instrumentName) {
              <div class="text-[0.6875rem] font-mono text-surface-400">{{ row.instrumentName }}</div>
            }
          </td>
          <td>
            @if (row.pair) {
              <app-asset-pair-badge [pairs]="[row.pair]" [maxVisible]="1"/>
            }
          </td>
          <td class="text-xs">
            @if (row.instrumentTypeId) {
              <a [routerLink]="['/settings/instrument-types', row.instrumentTypeId]" class="text-primary hover:underline">{{ getTypeDisplayName(row.instrumentTypeId) }}</a>
            }
          </td>
          <td>
            <p-tag [value]="row.isActive ? 'Active' : 'Inactive'" [severity]="row.isActive ? 'success' : 'secondary'" [rounded]="true"/>
          </td>
          <td>
            <p-button label="Remove" severity="danger" [text]="true" size="small" (onClick)="remove.emit(row.instrumentId)"/>
          </td>
        </tr>
      </ng-template>
      <ng-template #emptymessage>
        <tr>
          <td colspan="5">
            <app-empty-state title="No instruments" message="Add instruments to this universe." icon="data"/>
          </td>
        </tr>
      </ng-template>
    </p-table>
  `,
})
export class UniverseTableComponent {
  private assetService = inject(AssetService);

  items = input<UniverseItem[]>([]);
  @Output() remove = new EventEmitter<string>();

  pageSize = 10;

  rows = computed<UniverseRow[]>(() => {
    const instruments = this.assetService.instruments();
    const instrumentMap = new Map<string, Instrument>();
    for (const inst of instruments) instrumentMap.set(inst.id, inst);

    return this.items().map(item => {
      const inst = instrumentMap.get(item.instrument_id);
      const pair: AssetPair | null = inst ? {
        providerName: inst.provider_name ?? '',
        providerId: inst.provider_id,
        fromAssetName: inst.from_asset_name ?? '',
        fromAssetId: inst.from_asset_id,
        toAssetName: inst.to_asset_name ?? '',
        toAssetId: inst.to_asset_id,
      } : null;
      return {
        instrumentId: item.instrument_id,
        instrumentName: item.instrument_name ?? inst?.name ?? item.instrument_id,
        instrumentDisplayName: item.instrument_display_name ?? inst?.display_name ?? '',
        instrumentTypeId: item.instrument_type_id ?? inst?.instrument_type_id ?? '',
        isActive: item.is_active ?? inst?.is_active ?? true,
        pair,
        order: item.order,
      };
    }).sort((a, b) => a.order - b.order);
  });

  getTypeDisplayName(typeId: string): string {
    if (!typeId) return '';
    const t = this.assetService.instrumentTypes().find(t => t.id === typeId);
    return t?.display_name || t?.name || '';
  }
}
