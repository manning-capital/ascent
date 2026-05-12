import { Component, OnInit, computed, effect, inject, signal, untracked } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { MultiSelect } from 'primeng/multiselect';
import { DatePicker } from 'primeng/datepicker';
import { Button } from 'primeng/button';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { DataExplorerService } from '../../services/data-explorer.service';
import { AppPageHeaderComponent } from '../ui/page-header/app-page-header.component';
import { AppDataCellShellComponent } from './cells/app-data-cell-shell.component';
import { AppSeriesChipBarComponent } from './cells/app-series-chip-bar.component';
import { AppLineChartCellComponent } from './cells/app-line-chart-cell.component';
import { AppBarChartCellComponent } from './cells/app-bar-chart-cell.component';
import { AppScatterChartCellComponent } from './cells/app-scatter-chart-cell.component';
import { AppHistogramCellComponent } from './cells/app-histogram-cell.component';
import { AppTableCellComponent } from './cells/app-table-cell.component';
import { DataExplorerCursorService } from './cursor.service';
import {
  cellId,
  decodeWorkspace,
  encodeWorkspace,
  legacyWorkspace,
} from './state-codec';
import type {
  Cell,
  ChartCell,
  ChartCellKind,
  SeriesSpec,
  TableCell,
  WorkspaceState,
} from './types';
import { EMPTY_WORKSPACE } from './types';

const DEFAULT_HEIGHTS: Record<Cell['kind'], number> = {
  line: 280,
  bar: 280,
  scatter: 320,
  histogram: 260,
  table: 360,
};

const DEFAULT_TITLES: Record<Cell['kind'], string> = {
  line: 'Line chart',
  bar: 'Bar chart',
  scatter: 'Scatter',
  histogram: 'Histogram',
  table: 'Table',
};

function isChartCell(c: Cell): c is ChartCell {
  return c.kind !== 'table';
}

@Component({
  selector: 'app-data-explorer',
  standalone: true,
  providers: [DataExplorerCursorService],
  imports: [
    FormsModule,
    DragDropModule,
    Select,
    MultiSelect,
    DatePicker,
    Button,
    AppPageHeaderComponent,
    AppDataCellShellComponent,
    AppSeriesChipBarComponent,
    AppLineChartCellComponent,
    AppBarChartCellComponent,
    AppScatterChartCellComponent,
    AppHistogramCellComponent,
    AppTableCellComponent,
  ],
  templateUrl: './data-explorer.component.html',
})
export class DataExplorerComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  dataService = inject(DataExplorerService);

  state = signal<WorkspaceState>(EMPTY_WORKSPACE);

  // Convenience accessors used by the template
  table = computed(() => this.state().table);
  cells = computed(() => this.state().cells);
  start = computed(() => this.state().start);
  end = computed(() => this.state().end);
  entityIds = computed(() => this.state().entityIds);
  descriptorIds = computed(() => this.state().descriptorIds);
  periodIds = computed(() => this.state().periodIds);

  startDate = computed(() => {
    const s = this.start();
    return s ? new Date(s) : null;
  });
  endDate = computed(() => {
    const e = this.end();
    return e ? new Date(e) : null;
  });

  hasPeriod = computed(() => {
    const tbl = this.table();
    if (!tbl) return false;
    return this.dataService.dataSources().find((s) => s.table === tbl)?.has_period ?? false;
  });

  entityLabel = computed(() => this.dimensionLabel('entity'));
  descriptorLabel = computed(() => this.dimensionLabel('descriptor'));

  /** Bundle of available filter options + the workspace context, passed to
   *  every series chip bar so chips can render labels / dropdown options
   *  without each chart cell re-deriving them. */
  seriesOptions = computed(() => ({
    entities: this.dataService.filterOptions().entities,
    descriptors: this.dataService.filterOptions().descriptors,
    periods: this.dataService.filterOptions().periods,
  }));

  private urlWriteTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    // Sync state → URL (debounced 250ms). Reads the current state at write
    // time, not at scheduling time, so coalesced rapid edits persist the
    // final state, not whatever happened to be there when the timer was set.
    effect(() => {
      this.state();
      if (this.urlWriteTimer != null) clearTimeout(this.urlWriteTimer);
      this.urlWriteTimer = setTimeout(() => {
        this.urlWriteTimer = null;
        untracked(() => this.persistUrl(this.state()));
      }, 250);
    });

    // When the table or time window changes, drop the in-memory series cache
    // so chart cells re-fetch with the new context.
    effect(() => {
      this.state().table;
      this.state().start;
      this.state().end;
      untracked(() => this.dataService.clearSeriesCache());
    });
  }

  ngOnInit(): void {
    this.dataService.loadSources();
    const qp = this.route.snapshot.queryParamMap;

    // Prefer the new `state` param; fall back to legacy individual params
    // (table, start, end, entity_ids...) for back-compat with old bookmarks.
    const encoded = qp.get('state');
    let initial = decodeWorkspace(encoded);
    if (!initial) {
      initial = legacyWorkspace({
        table: qp.get('table'),
        start: qp.get('start'),
        end: qp.get('end'),
        entityIds: qp.getAll('entity_ids'),
        descriptorIds: qp.getAll('descriptor_ids'),
        periodIds: qp.getAll('period_ids'),
      });
    }
    this.state.set(initial);

    if (initial.table) {
      this.dataService.loadFilterOptions(initial.table);
    }
  }

  // ─── Workspace mutations ──────────────────────────────────
  onTableChange(table: string | null): void {
    this.state.update((s) => ({
      ...s,
      table,
      // Reset filter selections when source changes — different tables expose
      // different entity/descriptor pools.
      entityIds: [],
      descriptorIds: [],
      periodIds: [],
      cells: table && s.cells.length === 0 ? [this.makeCell('table')] : s.cells,
    }));
    if (table) this.dataService.loadFilterOptions(table);
  }

  onStartChange(d: Date | null): void {
    this.state.update((s) => ({ ...s, start: d ? d.toISOString() : null }));
  }

  onEndChange(d: Date | null): void {
    this.state.update((s) => ({ ...s, end: d ? d.toISOString() : null }));
  }

  onEntityIdsChange(ids: string[]): void {
    this.state.update((s) => ({ ...s, entityIds: ids }));
  }

  onDescriptorIdsChange(ids: string[]): void {
    this.state.update((s) => ({ ...s, descriptorIds: ids }));
  }

  onPeriodIdsChange(ids: string[]): void {
    this.state.update((s) => ({ ...s, periodIds: ids }));
  }

  clearFilters(): void {
    this.state.update((s) => ({
      ...s,
      start: null,
      end: null,
      entityIds: [],
      descriptorIds: [],
      periodIds: [],
    }));
  }

  // ─── Cell mutations ───────────────────────────────────────
  addCell(kind: Cell['kind']): void {
    this.state.update((s) => ({ ...s, cells: [...s.cells, this.makeCell(kind)] }));
  }

  private makeCell(kind: Cell['kind']): Cell {
    if (kind === 'table') {
      return { id: cellId(), kind: 'table', height: DEFAULT_HEIGHTS.table } satisfies TableCell;
    }
    return {
      id: cellId(),
      kind,
      series: [],
      bucket: kind === 'bar' ? 'day' : 'none',
      height: DEFAULT_HEIGHTS[kind],
    } satisfies ChartCell;
  }

  renameCell(id: string, title: string): void {
    this.updateCell(id, (c) => ({ ...c, title: title || undefined }));
  }

  deleteCell(id: string): void {
    this.state.update((s) => ({ ...s, cells: s.cells.filter((c) => c.id !== id) }));
  }

  duplicateCell(id: string): void {
    this.state.update((s) => {
      const idx = s.cells.findIndex((c) => c.id === id);
      if (idx < 0) return s;
      const copy: Cell = { ...s.cells[idx], id: cellId() };
      const cells = [...s.cells];
      cells.splice(idx + 1, 0, copy);
      return { ...s, cells };
    });
  }

  moveCell(id: string, direction: 1 | -1): void {
    this.state.update((s) => {
      const idx = s.cells.findIndex((c) => c.id === id);
      if (idx < 0) return s;
      const target = idx + direction;
      if (target < 0 || target >= s.cells.length) return s;
      const cells = [...s.cells];
      [cells[idx], cells[target]] = [cells[target], cells[idx]];
      return { ...s, cells };
    });
  }

  onDrop(event: CdkDragDrop<Cell[]>): void {
    if (event.previousIndex === event.currentIndex) return;
    this.state.update((s) => {
      const cells = [...s.cells];
      moveItemInArray(cells, event.previousIndex, event.currentIndex);
      return { ...s, cells };
    });
  }

  updateSeries(id: string, series: SeriesSpec[]): void {
    this.updateCell(id, (c) => (isChartCell(c) ? { ...c, series } : c));
  }

  resetWorkspace(): void {
    const tbl = this.table();
    this.state.update((s) => ({
      ...EMPTY_WORKSPACE,
      table: tbl,
      cells: tbl ? [this.makeCell('table')] : [],
    }));
  }

  // ─── Helpers ──────────────────────────────────────────────
  isChart(c: Cell): c is ChartCell {
    return isChartCell(c);
  }

  isTable(c: Cell): c is TableCell {
    return c.kind === 'table';
  }

  asChart(c: Cell): ChartCell {
    return c as ChartCell;
  }

  asTable(c: Cell): TableCell {
    return c as TableCell;
  }

  defaultTitleFor(kind: Cell['kind']): string {
    return DEFAULT_TITLES[kind];
  }

  private updateCell(id: string, fn: (c: Cell) => Cell): void {
    this.state.update((s) => ({
      ...s,
      cells: s.cells.map((c) => (c.id === id ? fn(c) : c)),
    }));
  }

  private dimensionLabel(kind: 'entity' | 'descriptor'): string {
    const tbl = this.table();
    if (!tbl) return kind === 'entity' ? 'Entities' : 'Fields';
    const source = this.dataService.dataSources().find((s) => s.table === tbl);
    if (!source) return kind === 'entity' ? 'Entities' : 'Fields';
    const t = kind === 'entity' ? source.entity_type : source.descriptor_type;
    return t.charAt(0).toUpperCase() + t.slice(1) + 's';
  }

  private persistUrl(state: WorkspaceState): void {
    const encoded = encodeWorkspace(state);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: encoded ? { state: encoded } : {},
      replaceUrl: true,
    });
  }
}
