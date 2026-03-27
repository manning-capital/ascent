import { Component, Input, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { DatePicker } from 'primeng/datepicker';
import { Splitter } from 'primeng/splitter';
import { RunDetailCardComponent, RunDetailItem, RunDetailField } from './run-detail-card.component';
import { PaginatedResponse } from '../../models/trade.model';

export type { RunDetailField };
export type RunItem = RunDetailItem;

export interface RunFilter {
  started_after?: string;
  started_before?: string;
}

type FilterMode = 'none' | 'range' | 'around';
type Radius = 5 | 10 | 30 | 60;

@Component({
  selector: 'app-run-viewer',
  standalone: true,
  imports: [DatePipe, FormsModule, DatePicker, Splitter, RunDetailCardComponent],
  template: `
    <p-splitter [panelSizes]="[60, 40]" [minSizes]="[25, 15]" [gutterSize]="6" class="h-full block">
      <ng-template #panel>
      <!-- Left: Selected Run Detail -->
      <div class="h-full overflow-y-auto">
        @if (selectedRun(); as run) {
          <div class="p-5">
            <app-run-detail-card [run]="run" [extraFields]="extraDetailFields"/>
          </div>
        } @else {
          <div class="flex items-center justify-center h-full text-sm text-fg-faint">
            Select a run to view details
          </div>
        }
      </div>
      </ng-template>

      <ng-template #panel>
      <!-- Right: Run List with Filters -->
      <div class="h-full flex flex-col">
        <!-- Filter bar -->
        <div class="px-3 py-2 border-b border-edge shrink-0 space-y-2">
          <div class="flex items-center gap-1.5">
            <span class="text-[11px] text-fg-faint mr-1">Filter:</span>
            <button
              (click)="setFilterMode('none')"
              class="px-2 py-0.5 rounded text-[11px] transition-colors"
              [class]="filterMode() === 'none' ? 'bg-info/20 text-info' : 'text-fg-muted hover:text-fg hover:bg-fg/5'">
              All
            </button>
            <button
              (click)="setFilterMode('range')"
              class="px-2 py-0.5 rounded text-[11px] transition-colors"
              [class]="filterMode() === 'range' ? 'bg-info/20 text-info' : 'text-fg-muted hover:text-fg hover:bg-fg/5'">
              Range
            </button>
            <button
              (click)="setFilterMode('around')"
              class="px-2 py-0.5 rounded text-[11px] transition-colors"
              [class]="filterMode() === 'around' ? 'bg-info/20 text-info' : 'text-fg-muted hover:text-fg hover:bg-fg/5'">
              Around
            </button>
          </div>

          <!-- Range filter inputs -->
          @if (filterMode() === 'range') {
            <div class="space-y-1.5">
              <div class="flex items-center gap-2">
                <label class="text-[10px] text-fg-faint w-10 shrink-0">From</label>
                <p-datepicker
                  [ngModel]="rangeFrom()"
                  (ngModelChange)="rangeFrom.set($event)"
                  [showTime]="true"
                  dateFormat="yy-mm-dd"
                  hourFormat="24"
                  [style]="{'width': '100%'}"/>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-[10px] text-fg-faint w-10 shrink-0">To</label>
                <p-datepicker
                  [ngModel]="rangeTo()"
                  (ngModelChange)="rangeTo.set($event)"
                  [showTime]="true"
                  dateFormat="yy-mm-dd"
                  hourFormat="24"
                  [style]="{'width': '100%'}"/>
              </div>
              <div class="flex gap-1.5">
                <button
                  (click)="applyFilter()"
                  class="flex-1 py-1 rounded text-[11px] bg-info/20 text-info hover:bg-info/30 transition-colors">
                  Apply
                </button>
                <button
                  (click)="clearFilter()"
                  class="px-2 py-1 rounded text-[11px] text-fg-muted hover:text-fg hover:bg-fg/5 transition-colors">
                  Clear
                </button>
              </div>
            </div>
          }

          <!-- Around filter inputs -->
          @if (filterMode() === 'around') {
            <div class="space-y-1.5">
              <p-datepicker
                [ngModel]="aroundDatetime()"
                (ngModelChange)="aroundDatetime.set($event)"
                [showTime]="true"
                dateFormat="yy-mm-dd"
                hourFormat="24"
                [style]="{'width': '100%'}"/>
              <div class="flex items-center gap-1">
                <span class="text-[10px] text-fg-faint shrink-0">&plusmn;</span>
                @for (r of radiusOptions; track r) {
                  <button
                    (click)="aroundRadius.set(r)"
                    class="px-2 py-0.5 rounded text-[11px] transition-colors"
                    [class]="aroundRadius() === r ? 'bg-info/20 text-info' : 'text-fg-muted hover:text-fg hover:bg-fg/5'">
                    {{ radiusLabel(r) }}
                  </button>
                }
              </div>
              <div class="flex gap-1.5">
                <button
                  (click)="applyFilter()"
                  class="flex-1 py-1 rounded text-[11px] bg-info/20 text-info hover:bg-info/30 transition-colors">
                  Apply
                </button>
                <button
                  (click)="clearFilter()"
                  class="px-2 py-1 rounded text-[11px] text-fg-muted hover:text-fg hover:bg-fg/5 transition-colors">
                  Clear
                </button>
              </div>
            </div>
          }
        </div>

        <!-- Run count -->
        <div class="px-3 py-2 border-b border-edge shrink-0">
          <p class="text-[11px] text-fg-faint">{{ total() }} runs</p>
        </div>

        <!-- Run list -->
        <div class="flex-1 overflow-y-auto">
          @for (run of runs(); track run.id) {
            <div
              (click)="selectRun(run)"
              class="px-3 py-2.5 border-b border-edge-dim cursor-pointer transition-colors"
              [class]="selectedRun()?.id === run.id ? 'bg-info/10 border-l-2 border-l-info' : 'hover:bg-fg/[.03]'">
              <div class="flex items-center justify-between mb-0.5">
                <div class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full shrink-0" [class]="statusDotClass(run.status)"></span>
                  <span class="text-[11px] font-medium" [class]="statusClass(run.status)">{{ run.status }}</span>
                </div>
                <span class="text-[10px] text-fg-faint">#{{ run.id }}</span>
              </div>
              <div class="text-[10px] text-fg-faint flex items-center justify-between">
                <span>{{ run.started_at | date:'MMM d, h:mm:ss a' }}</span>
                <span>{{ durationLabel(run) }}</span>
              </div>
              @if (run.error_message) {
                <p class="text-[10px] text-negative mt-0.5 line-clamp-1">{{ run.error_message }}</p>
              }
            </div>
          } @empty {
            <div class="flex items-center justify-center h-32 text-sm text-fg-faint">No runs found.</div>
          }
        </div>

        <!-- Pagination -->
        <div class="flex items-center justify-between px-3 py-2 border-t border-edge shrink-0 text-[11px] text-fg-muted">
          <span>Page {{ page() }} / {{ totalPages() || 1 }}</span>
          <div class="flex items-center gap-1.5">
            <button
              [disabled]="page() <= 1"
              (click)="onPageChange(page() - 1)"
              class="px-2 py-0.5 rounded border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors">
              Prev
            </button>
            <button
              [disabled]="page() >= totalPages()"
              (click)="onPageChange(page() + 1)"
              class="px-2 py-0.5 rounded border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors">
              Next
            </button>
          </div>
        </div>
      </div>
      </ng-template>
    </p-splitter>
  `,
})
export class RunViewerComponent implements OnInit {
  @Input() loadFn!: (page: number, pageSize: number, filter?: RunFilter) => Observable<PaginatedResponse<RunItem>>;
  @Input() extraDetailFields: RunDetailField[] = [];
  @Input() pageSize = 20;
  @Input() initialRunId: string | null = null;

  runs = signal<RunItem[]>([]);
  total = signal(0);
  totalPages = signal(0);
  page = signal(1);
  selectedRun = signal<RunItem | null>(null);

  // Filter state
  filterMode = signal<FilterMode>('none');
  rangeFrom = signal<Date | null>(null);
  rangeTo = signal<Date | null>(null);
  aroundDatetime = signal<Date | null>(null);
  aroundRadius = signal<Radius>(5);
  radiusOptions: Radius[] = [5, 10, 30, 60];

  ngOnInit(): void {
    this.loadRuns();
  }

  selectRun(run: RunItem): void {
    this.selectedRun.set(run);
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.loadRuns();
  }

  setFilterMode(mode: FilterMode): void {
    this.filterMode.set(mode);
    if (mode === 'none') {
      this.rangeFrom.set(null);
      this.rangeTo.set(null);
      this.aroundDatetime.set(null);
      this.page.set(1);
      this.loadRuns();
    }
  }

  applyFilter(): void {
    this.page.set(1);
    this.selectedRun.set(null);
    this.loadRuns();
  }

  clearFilter(): void {
    this.setFilterMode('none');
  }

  private loadRuns(): void {
    this.loadFn(this.page(), this.pageSize, this.buildFilter()).subscribe({
      next: (res) => {
        this.runs.set(res.items);
        this.total.set(res.total);
        this.totalPages.set(res.total_pages);
        if (this.initialRunId && !this.selectedRun()) {
          const match = res.items.find(r => r.id === this.initialRunId);
          if (match) this.selectedRun.set(match);
        }
      },
    });
  }

  private buildFilter(): RunFilter | undefined {
    const mode = this.filterMode();
    if (mode === 'range') {
      const f: RunFilter = {};
      const from = this.rangeFrom();
      const to = this.rangeTo();
      if (from) f.started_after = from.toISOString();
      if (to) f.started_before = to.toISOString();
      if (f.started_after || f.started_before) return f;
    } else if (mode === 'around') {
      const center = this.aroundDatetime();
      if (center) {
        const offsetMs = this.aroundRadius() * 60 * 1000;
        return {
          started_after: new Date(center.getTime() - offsetMs).toISOString(),
          started_before: new Date(center.getTime() + offsetMs).toISOString(),
        };
      }
    }
    return undefined;
  }

  radiusLabel(r: number): string {
    if (r < 60) return `${r}m`;
    return `${r / 60}h`;
  }

  statusClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'text-positive';
      case 'FAILED': return 'text-negative';
      case 'RUNNING': return 'text-warning';
      case 'PENDING': return 'text-fg-muted';
      default: return '';
    }
  }

  statusDotClass(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'bg-positive';
      case 'FAILED': return 'bg-negative';
      case 'RUNNING': return 'bg-warning animate-pulse';
      case 'PENDING': return 'bg-fg-faint';
      default: return 'bg-fg-faint';
    }
  }

  durationLabel(run: RunItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
