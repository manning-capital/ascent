import { Component, Input, Output, EventEmitter } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Button } from 'primeng/button';
import { EmptyStateComponent } from './empty-state.component';
import { AssetPairBadgeComponent, AssetPair } from './asset-pair-badge.component';
import { UniverseItem } from '../../models/asset.model';

/** A flattened row for the combined universe table. */
interface UniverseRow {
  items: UniverseItem[];
  isGroup: boolean;
  groupId: string | null;
  memberCount: number;
}

@Component({
  selector: 'app-universe-table',
  standalone: true,
  imports: [RouterLink, TableModule, Button, EmptyStateComponent, AssetPairBadgeComponent],
  styles: [`
    :host ::ng-deep .p-datatable {
      border-radius: 0.5rem;
      overflow: hidden;
    }
  `],
  template: `
    <p-table [value]="rows" [paginator]="true" [rows]="pageSize" [showCurrentPageReport]="true"
             currentPageReportTemplate="{first}–{last} of {totalRecords}" [rowsPerPageOptions]="[5, 10, 25]">
      <ng-template #header>
        <tr>
          <th class="w-12">#</th>
          <th>Pairs</th>
          <th class="w-24 text-center">Members</th>
          <th>Group</th>
          <th class="w-20"></th>
        </tr>
      </ng-template>
      <ng-template #body let-row let-i="rowIndex">
        <tr>
          <td class="text-surface-500 font-mono text-xs">{{ i + 1 }}</td>
          <td>
            <app-asset-pair-badge [pairs]="toPairs(row.items)"/>
          </td>
          <td class="text-center font-mono text-xs text-surface-500">{{ row.memberCount }}</td>
          <td>
            @if (row.groupId) {
              <a [routerLink]="['/settings/asset-groups', row.groupId]" class="text-xs text-primary hover:underline">View Group</a>
            } @else {
              <span class="text-xs text-surface-400">–</span>
            }
          </td>
          <td>
            @if (row.isGroup) {
              <p-button label="Remove" severity="danger" [text]="true" size="small" (onClick)="removeGroup.emit(row.items)"/>
            } @else {
              <p-button label="Remove" severity="danger" [text]="true" size="small" (onClick)="remove.emit(row.items[0])"/>
            }
          </td>
        </tr>
      </ng-template>
      <ng-template #emptymessage>
        <tr>
          <td colspan="5">
            <app-empty-state title="No universe items" message="Add asset pairs or link asset groups to this universe." icon="inbox"/>
          </td>
        </tr>
      </ng-template>
    </p-table>
  `,
})
export class UniverseTableComponent {
  @Input() items: UniverseItem[] = [];
  @Output() remove = new EventEmitter<UniverseItem>();
  @Output() removeGroup = new EventEmitter<UniverseItem[]>();

  pageSize = 10;

  toPairs(items: UniverseItem[]): AssetPair[] {
    return items.map(m => ({
      providerName: m.provider_name ?? '',
      providerId: m.provider_id,
      fromAssetSymbol: m.from_asset_symbol ?? '',
      fromAssetId: m.from_asset_id,
      toAssetSymbol: m.to_asset_symbol ?? '',
      toAssetId: m.to_asset_id,
    }));
  }

  get rows(): UniverseRow[] {
    const groupMap = new Map<string, UniverseItem[]>();

    for (const item of this.items) {
      const existing = groupMap.get(item.provider_asset_group_id) || [];
      existing.push(item);
      groupMap.set(item.provider_asset_group_id, existing);
    }

    const rows: UniverseRow[] = [];

    for (const [groupId, items] of groupMap) {
      const sorted = items.sort((a, b) => a.order - b.order);
      const isMultiMember = sorted.length > 1;
      rows.push({
        items: sorted,
        isGroup: isMultiMember,
        groupId: groupId,
        memberCount: sorted.length,
      });
    }

    return rows;
  }
}
