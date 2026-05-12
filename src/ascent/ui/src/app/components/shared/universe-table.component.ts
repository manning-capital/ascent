import {
  Component,
  computed,
  inject,
  input,
  EventEmitter,
  Output,
  TemplateRef,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { AppDataTableComponent } from '../ui/data-table/app-data-table.component';
import { AppEmptyStateComponent } from '../ui/empty-state/app-empty-state.component';
import { AppStatusBadgeComponent } from '../ui/status-badge/app-status-badge.component';
import type { AppColumn } from '../ui/data-table/app-column.model';
import { AssetPairBadgeComponent, AssetPair } from './asset-pair-badge.component';
import { UniverseItem, Instrument } from '../../models/asset.model';
import { AssetService } from '../../services/asset.service';

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
  imports: [
    RouterLink,
    Button,
    AppDataTableComponent,
    AppEmptyStateComponent,
    AppStatusBadgeComponent,
    AssetPairBadgeComponent,
  ],
  template: `
    @if (rows().length === 0) {
      <app-empty-state title="No instruments" message="Add instruments to this universe." />
    } @else {
      <app-data-table
        class="block"
        [value]="rows()"
        [columns]="columns()"
        [pageSize]="10"
        [edgeToEdge]="false"
      />
    }

    <ng-template #nameTpl let-row>
      <div class="flex flex-col gap-0.5">
        <a
          [routerLink]="['/settings/master-data/instruments', row.instrumentId]"
          (click)="$event.stopPropagation()"
          class="text-primary hover:underline font-medium text-sm"
        >
          {{ row.instrumentDisplayName || row.instrumentName }}
        </a>
        @if (row.instrumentDisplayName && row.instrumentName) {
          <span class="text-[11px] font-mono text-fg-faint">{{ row.instrumentName }}</span>
        }
      </div>
    </ng-template>

    <ng-template #pairTpl let-row>
      @if (row.pair) {
        <app-asset-pair-badge [pairs]="[row.pair]" [maxVisible]="1" />
      }
    </ng-template>

    <ng-template #typeTpl let-row>
      @if (row.instrumentTypeId) {
        <a
          [routerLink]="['/settings/types/instrument-types', row.instrumentTypeId]"
          (click)="$event.stopPropagation()"
          class="text-primary hover:underline text-xs"
        >
          {{ typeName(row.instrumentTypeId) }}
        </a>
      }
    </ng-template>

    <ng-template #statusTpl let-row>
      <app-status-badge [value]="row.isActive ? 'Active' : 'Inactive'" />
    </ng-template>

    <ng-template #removeTpl let-row>
      <p-button
        label="Remove"
        severity="danger"
        [text]="true"
        size="small"
        (onClick)="onRemove($event, row.instrumentId)"
      />
    </ng-template>
  `,
})
export class UniverseTableComponent {
  private assetService = inject(AssetService);

  items = input<UniverseItem[]>([]);
  @Output() remove = new EventEmitter<string>();

  nameTpl = viewChild.required<TemplateRef<{ $implicit: UniverseRow }>>('nameTpl');
  pairTpl = viewChild.required<TemplateRef<{ $implicit: UniverseRow }>>('pairTpl');
  typeTpl = viewChild.required<TemplateRef<{ $implicit: UniverseRow }>>('typeTpl');
  statusTpl = viewChild.required<TemplateRef<{ $implicit: UniverseRow }>>('statusTpl');
  removeTpl = viewChild.required<TemplateRef<{ $implicit: UniverseRow }>>('removeTpl');

  columns = computed<AppColumn<UniverseRow>[]>(() => [
    { field: 'instrumentDisplayName', header: 'Instrument', cellTemplate: this.nameTpl(), minWidth: 200 },
    { field: 'pair', header: 'Pair', sortable: false, cellTemplate: this.pairTpl(), minWidth: 200 },
    { field: 'instrumentTypeId', header: 'Type', cellTemplate: this.typeTpl(), minWidth: 140 },
    { field: 'isActive', header: 'Status', cellTemplate: this.statusTpl(), width: 96 },
    { field: 'instrumentId' as any, header: '', sortable: false, cellTemplate: this.removeTpl(), width: 96 },
  ]);

  rows = computed<UniverseRow[]>(() => {
    const instruments = this.assetService.instruments();
    const instrumentMap = new Map<string, Instrument>();
    for (const inst of instruments) instrumentMap.set(inst.id, inst);

    return this.items()
      .map((item) => {
        const inst = instrumentMap.get(item.instrument_id);
        const pair: AssetPair | null = inst
          ? {
              providerName: inst.provider_name ?? '',
              providerId: inst.provider_id,
              fromAssetName: inst.from_asset_name ?? '',
              fromAssetId: inst.from_asset_id,
              toAssetName: inst.to_asset_name ?? '',
              toAssetId: inst.to_asset_id,
            }
          : null;
        return {
          instrumentId: item.instrument_id,
          instrumentName: item.instrument_name ?? inst?.name ?? item.instrument_id,
          instrumentDisplayName: item.instrument_display_name ?? inst?.display_name ?? '',
          instrumentTypeId: item.instrument_type_id ?? inst?.instrument_type_id ?? '',
          isActive: item.is_active ?? inst?.is_active ?? true,
          pair,
          order: item.order,
        };
      })
      .sort((a, b) => a.order - b.order);
  });

  typeName(typeId: string): string {
    if (!typeId) return '';
    const t = this.assetService.instrumentTypes().find((tp) => tp.id === typeId);
    return t?.display_name || t?.name || '';
  }

  onRemove(event: Event, instrumentId: string): void {
    event.stopPropagation();
    this.remove.emit(instrumentId);
  }
}
