import { Component, Input, Output, EventEmitter } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Button } from 'primeng/button';
import { EmptyStateComponent } from './empty-state.component';
import { UniverseItem } from '../../models/asset.model';

/** A flattened row for the combined universe table. */
interface UniverseRow {
  /** The universe items — multiple for a group, single for an individual pair. */
  items: UniverseItem[];
  /** True if this row represents a group. */
  isGroup: boolean;
  /** The group ID (null for individual pairs). */
  groupId: string | null;
  /** Number of members (1 for individual pairs). */
  memberCount: number;
}

@Component({
  selector: 'app-universe-table',
  standalone: true,
  imports: [RouterLink, TableModule, Button, EmptyStateComponent],
  template: `
    <p-table [value]="rows" [paginator]="true" [rows]="pageSize" [showCurrentPageReport]="true"
             currentPageReportTemplate="{first}–{last} of {totalRecords}" [rowsPerPageOptions]="[5, 10, 25]">
      <ng-template #header>
        <tr>
          <th class="w-12">#</th>
          <th>Assets</th>
          <th class="w-24 text-center">Members</th>
          <th>Group</th>
          <th class="w-20"></th>
        </tr>
      </ng-template>
      <ng-template #body let-row let-i="rowIndex">
        <tr>
          <td class="text-surface-500 font-mono text-xs">{{ i + 1 }}</td>
          <td>
            <div class="flex flex-wrap gap-1.5">
              @for (m of row.items; track m.order) {
                <span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-canvas/50 border border-surface">
                  <a [routerLink]="['/settings/assets', m.from_asset_id]" class="font-medium text-primary hover:underline">{{ m.from_asset_symbol }}</a>
                  <span class="text-surface-400">&rarr;</span>
                  <a [routerLink]="['/settings/assets', m.to_asset_id]" class="font-medium text-primary hover:underline">{{ m.to_asset_symbol }}</a>
                </span>
              }
            </div>
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

  get rows(): UniverseRow[] {
    const groupMap = new Map<string, UniverseItem[]>();
    const individuals: UniverseItem[] = [];

    for (const item of this.items) {
      if (item.provider_asset_group_id) {
        const existing = groupMap.get(item.provider_asset_group_id) || [];
        existing.push(item);
        groupMap.set(item.provider_asset_group_id, existing);
      } else {
        individuals.push(item);
      }
    }

    const rows: UniverseRow[] = [];

    // Groups first
    for (const [groupId, items] of groupMap) {
      rows.push({
        items: items.sort((a, b) => a.order - b.order),
        isGroup: true,
        groupId,
        memberCount: items.length,
      });
    }

    // Individual pairs
    for (const item of individuals) {
      rows.push({
        items: [item],
        isGroup: false,
        groupId: null,
        memberCount: 1,
      });
    }

    return rows;
  }
}
