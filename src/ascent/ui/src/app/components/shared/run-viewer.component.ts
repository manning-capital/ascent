import { Component, Input, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { DatePicker } from 'primeng/datepicker';
import { Splitter } from 'primeng/splitter';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Paginator } from 'primeng/paginator';
import { Message } from 'primeng/message';
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
  imports: [DatePipe, FormsModule, DatePicker, Splitter, SelectButton, Button, Tag, Paginator, Message, RunDetailCardComponent],
  template: `
    <p-splitter [panelSizes]="[60, 40]" [minSizes]="[25, 15]" [gutterSize]="6" class="h-full">
      <ng-template #panel>
      <!-- Left: Selected Run Detail -->
      <div class="h-full overflow-y-auto">
        @if (selectedRun(); as run) {
          <div class="p-4">
            <app-run-detail-card [run]="run" [extraFields]="extraDetailFields"/>
          </div>
        } @else {
          <div class="flex items-center justify-center h-full">
            <p-message severity="secondary">Select a run to view details</p-message>
          </div>
        }
      </div>
      </ng-template>

      <ng-template #panel>
      <!-- Right: Run List with Filters -->
      <div class="h-full flex flex-col">
        <!-- Filter bar -->
        <div class="p-3 shrink-0 space-y-2">
          <p-selectButton
            [options]="filterOptions"
            [ngModel]="filterMode()"
            (ngModelChange)="setFilterMode($event)"
            optionLabel="label"
            optionValue="value"
            size="small"/>

          <!-- Range filter inputs -->
          @if (filterMode() === 'range') {
            <div class="flex flex-col gap-2">
              <div class="flex items-center gap-2">
                <label class="text-xs text-surface-500 w-10 shrink-0">From</label>
                <p-datepicker
                  [ngModel]="rangeFrom()"
                  (ngModelChange)="rangeFrom.set($event)"
                  [showTime]="true"
                  dateFormat="yy-mm-dd"
                  hourFormat="24"
                  [fluid]="true"/>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-surface-500 w-10 shrink-0">To</label>
                <p-datepicker
                  [ngModel]="rangeTo()"
                  (ngModelChange)="rangeTo.set($event)"
                  [showTime]="true"
                  dateFormat="yy-mm-dd"
                  hourFormat="24"
                  [fluid]="true"/>
              </div>
              <div class="flex gap-2">
                <p-button label="Apply" severity="info" size="small" (onClick)="applyFilter()" [fluid]="true"/>
                <p-button label="Clear" severity="secondary" size="small" [text]="true" (onClick)="clearFilter()"/>
              </div>
            </div>
          }

          <!-- Around filter inputs -->
          @if (filterMode() === 'around') {
            <div class="flex flex-col gap-2">
              <p-datepicker
                [ngModel]="aroundDatetime()"
                (ngModelChange)="aroundDatetime.set($event)"
                [showTime]="true"
                dateFormat="yy-mm-dd"
                hourFormat="24"
                [fluid]="true"/>
              <p-selectButton
                [options]="radiusSelectOptions"
                [ngModel]="aroundRadius()"
                (ngModelChange)="aroundRadius.set($event)"
                optionLabel="label"
                optionValue="value"
                size="small"/>
              <div class="flex gap-2">
                <p-button label="Apply" severity="info" size="small" (onClick)="applyFilter()" [fluid]="true"/>
                <p-button label="Clear" severity="secondary" size="small" [text]="true" (onClick)="clearFilter()"/>
              </div>
            </div>
          }
        </div>

        <!-- Run count -->
        <div class="px-3 py-2 shrink-0">
          <span class="text-xs text-surface-500">{{ total() }} runs</span>
        </div>

        <!-- Run list -->
        <div class="flex-1 overflow-y-auto min-h-0">
          @for (run of runs(); track run.id) {
            <div
              (click)="selectRun(run)"
              class="px-3 py-2.5 cursor-pointer transition-colors border-b border-surface"
              [class.bg-highlight]="selectedRun()?.id === run.id"
              [class.hover:bg-emphasis]="selectedRun()?.id !== run.id">
              <div class="flex items-center justify-between mb-1">
                <p-tag [value]="run.status" [severity]="statusSeverity(run.status)" [rounded]="true"/>
                <span class="text-xs text-surface-500">#{{ run.id }}</span>
              </div>
              <div class="text-xs text-surface-500 flex items-center justify-between">
                <span>{{ run.started_at | date:'MMM d, h:mm:ss a' }}</span>
                <span>{{ durationLabel(run) }}</span>
              </div>
              @if (run.error_message) {
                <p class="text-xs text-red-500 mt-1 line-clamp-1">{{ run.error_message }}</p>
              }
            </div>
          } @empty {
            <div class="flex items-center justify-center py-8 text-sm text-surface-400">No runs found.</div>
          }
        </div>

        <!-- Pagination -->
        <p-paginator
          [rows]="pageSize"
          [totalRecords]="total()"
          [first]="(page() - 1) * pageSize"
          (onPageChange)="onPageChange(($event.page ?? 0) + 1)"
          class="shrink-0"/>
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

  filterOptions = [
    { label: 'All', value: 'none' },
    { label: 'Range', value: 'range' },
    { label: 'Around', value: 'around' },
  ];

  radiusSelectOptions = [
    { label: '5m', value: 5 },
    { label: '10m', value: 10 },
    { label: '30m', value: 30 },
    { label: '1h', value: 60 },
  ];

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

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'info';
    }
  }

  durationLabel(run: RunItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
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
}
