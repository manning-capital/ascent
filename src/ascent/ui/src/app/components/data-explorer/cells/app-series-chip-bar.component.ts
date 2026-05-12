import { Component, computed, inject, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { ChartTokensService } from '../../ui/chart-canvas/chart-tokens.service';
import type { FilterOption } from '../../../models/data-explorer.model';
import type { Aggregation, ChartCellKind, SeriesSpec } from '../types';
import { cellId } from '../state-codec';

interface SeriesAvailableOptions {
  entities: FilterOption[];
  descriptors: FilterOption[];
  periods: FilterOption[] | null;
}

const AGGREGATION_OPTIONS: { label: string; value: Aggregation | 'none' }[] = [
  { label: 'Raw', value: 'none' },
  { label: 'Mean', value: 'mean' },
  { label: 'Sum', value: 'sum' },
  { label: 'Min', value: 'min' },
  { label: 'Max', value: 'max' },
  { label: 'Count', value: 'count' },
];

/** Horizontal chip bar that lets the user inspect, edit, add, and remove
 *  series for a chart cell. Each chip shows its color swatch (from the
 *  workspace chart-token palette), entity, and descriptor. Clicking opens
 *  a popover with the full series configuration form. */
@Component({
  selector: 'app-series-chip-bar',
  standalone: true,
  imports: [FormsModule, Button, Popover, Select],
  template: `
    <div class="flex items-center flex-wrap gap-1.5 px-2 py-1.5 border-t border-edge bg-canvas">
      @for (s of series(); track s.id; let i = $index) {
        <button
          type="button"
          class="flex items-center gap-1.5 pl-1 pr-2 py-0.5 rounded-md border border-edge bg-surface hover:bg-edge-dim text-[11px]"
          (click)="openEdit($event, i)"
        >
          <span class="inline-block w-2 h-2 rounded-full" [style.background]="colorAt(i)"></span>
          <span class="font-medium text-fg truncate" style="max-width: 8rem;">{{ entityLabel(s) }}</span>
          <span class="text-fg-faint">·</span>
          <span class="text-fg-muted truncate" style="max-width: 8rem;">{{ descriptorLabel(s) }}</span>
          @if (s.aggregation && s.aggregation !== 'mean') {
            <span class="text-fg-faint">·</span>
            <span class="text-fg-faint">{{ s.aggregation }}</span>
          }
        </button>
      }

      @if (canAddMore()) {
        <p-button
          icon="pi pi-plus"
          label="Series"
          severity="secondary"
          [text]="true"
          size="small"
          class="text-[11px]"
          (onClick)="openAdd($event)"
        />
      }
    </div>

    <p-popover #editPop appendTo="body" [style]="{ width: '20rem' }">
      <div class="flex flex-col gap-2 p-1">
        <h4 class="text-[11px] uppercase tracking-wider text-fg-faint mb-0">Series</h4>

        <label class="text-[11px] text-fg-muted">Entity</label>
        <p-select
          [options]="options().entities"
          optionLabel="display_name"
          optionValue="id"
          [(ngModel)]="draftEntityId"
          [filter]="true"
          appendTo="body"
          size="small"
          class="text-xs"
        />

        <label class="text-[11px] text-fg-muted">Descriptor</label>
        <p-select
          [options]="options().descriptors"
          optionLabel="display_name"
          optionValue="id"
          [(ngModel)]="draftDescriptorId"
          [filter]="true"
          appendTo="body"
          size="small"
          class="text-xs"
        />

        @if (options().periods?.length) {
          <label class="text-[11px] text-fg-muted">Period (optional)</label>
          <p-select
            [options]="periodOptions()"
            optionLabel="label"
            optionValue="value"
            [(ngModel)]="draftPeriodId"
            appendTo="body"
            size="small"
            class="text-xs"
          />
        }

        @if (kind() === 'line' || kind() === 'bar') {
          <label class="text-[11px] text-fg-muted">Aggregation</label>
          <p-select
            [options]="aggregationOptions"
            optionLabel="label"
            optionValue="value"
            [(ngModel)]="draftAggregation"
            appendTo="body"
            size="small"
            class="text-xs"
          />

          <label class="text-[11px] text-fg-muted">Y-axis</label>
          <p-select
            [options]="axisOptions"
            optionLabel="label"
            optionValue="value"
            [(ngModel)]="draftAxis"
            appendTo="body"
            size="small"
            class="text-xs"
          />
        }

        <div class="flex items-center justify-between gap-2 pt-1">
          @if (mode() === 'edit') {
            <p-button
              icon="pi pi-trash"
              label="Remove"
              severity="danger"
              [text]="true"
              size="small"
              (onClick)="removeCurrent()"
            />
          } @else {
            <span></span>
          }
          <div class="flex items-center gap-2">
            <p-button
              label="Cancel"
              severity="secondary"
              [text]="true"
              size="small"
              (onClick)="closePopover()"
            />
            <p-button
              [label]="mode() === 'edit' ? 'Save' : 'Add'"
              size="small"
              [disabled]="!draftEntityId || !draftDescriptorId"
              (onClick)="commit()"
            />
          </div>
        </div>
      </div>
    </p-popover>
  `,
})
export class AppSeriesChipBarComponent {
  series = input.required<SeriesSpec[]>();
  options = input.required<SeriesAvailableOptions>();
  kind = input.required<ChartCellKind>();

  seriesChange = output<SeriesSpec[]>();

  private tokens = inject(ChartTokensService);
  private editPop = viewChild<Popover>('editPop');

  readonly editingIndex = signal<number | null>(null);
  readonly mode = computed(() => (this.editingIndex() === null ? 'add' : 'edit'));

  draftEntityId = '';
  draftDescriptorId = '';
  draftPeriodId: string | null = null;
  draftAggregation: Aggregation | 'none' = 'mean';
  draftAxis: 'left' | 'right' = 'left';

  aggregationOptions = AGGREGATION_OPTIONS;
  axisOptions = [
    { label: 'Left', value: 'left' },
    { label: 'Right', value: 'right' },
  ];

  periodOptions = computed(() => {
    const p = this.options().periods ?? [];
    return [
      { label: 'All periods', value: null as string | null },
      ...p.map((o) => ({ label: o.display_name, value: o.id as string | null })),
    ];
  });

  /** scatter requires exactly 2 series, histogram exactly 1, line/bar unlimited. */
  canAddMore = computed(() => {
    const k = this.kind();
    const n = this.series().length;
    if (k === 'histogram') return n === 0;
    if (k === 'scatter') return n < 2;
    return true;
  });

  // ─── Color palette ────────────────────────────────────────
  colorAt(i: number): string {
    const t = this.tokens.tokens();
    const palette = [t.graphAccent1, t.graphAccent2, t.graphAccent3, t.graphAccent4, t.graphAccent5];
    return palette[i % palette.length] || t.fg;
  }

  // ─── Labels ───────────────────────────────────────────────
  entityLabel(s: SeriesSpec): string {
    return (
      s.label?.trim() ||
      this.options().entities.find((e) => e.id === s.entityId)?.display_name ||
      '?'
    );
  }

  descriptorLabel(s: SeriesSpec): string {
    return this.options().descriptors.find((d) => d.id === s.descriptorId)?.display_name || '?';
  }

  // ─── Popover handling ─────────────────────────────────────
  openAdd(event: Event): void {
    this.editingIndex.set(null);
    this.draftEntityId = '';
    this.draftDescriptorId = '';
    this.draftPeriodId = null;
    this.draftAggregation = 'mean';
    this.draftAxis = 'left';
    this.editPop()?.toggle(event);
  }

  openEdit(event: Event, index: number): void {
    const s = this.series()[index];
    if (!s) return;
    this.editingIndex.set(index);
    this.draftEntityId = s.entityId;
    this.draftDescriptorId = s.descriptorId;
    this.draftPeriodId = s.periodId ?? null;
    this.draftAggregation = s.aggregation ?? 'mean';
    this.draftAxis = s.axis ?? 'left';
    this.editPop()?.toggle(event);
  }

  closePopover(): void {
    this.editPop()?.hide();
  }

  commit(): void {
    if (!this.draftEntityId || !this.draftDescriptorId) return;
    const idx = this.editingIndex();
    const next: SeriesSpec = {
      id: idx === null ? cellId() : this.series()[idx].id,
      entityId: this.draftEntityId,
      descriptorId: this.draftDescriptorId,
      periodId: this.draftPeriodId ?? undefined,
      aggregation: this.draftAggregation === 'none' ? undefined : this.draftAggregation,
      axis: this.draftAxis,
    };
    const list = [...this.series()];
    if (idx === null) list.push(next);
    else list[idx] = next;
    this.seriesChange.emit(list);
    this.closePopover();
  }

  removeCurrent(): void {
    const idx = this.editingIndex();
    if (idx === null) return;
    const list = this.series().filter((_, i) => i !== idx);
    this.seriesChange.emit(list);
    this.closePopover();
  }
}
