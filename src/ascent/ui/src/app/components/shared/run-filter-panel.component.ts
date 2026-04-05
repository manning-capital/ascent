import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import type { RunFilter } from './run-viewer.component';

const PRESET_MS: Record<string, number> = {
  '1h': 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
};

@Component({
  selector: 'app-run-filter-panel',
  standalone: true,
  imports: [FormsModule, Select, DatePicker, SelectButton, Button],
  template: `
    <div class="rounded-lg border border-edge bg-surface p-4 mb-4 space-y-3">
      <!-- Top row: Status + Date Range -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-surface-500 mb-1">Status</label>
          <p-select
            [ngModel]="status()"
            (ngModelChange)="onStatusChange($event)"
            [options]="statusOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="All Statuses"
            [showClear]="true"
            class="w-full"/>
        </div>
        <div>
          <label class="block text-xs text-surface-500 mb-1">From</label>
          <p-datepicker
            [ngModel]="startDate()"
            (ngModelChange)="onStartDateChange($event)"
            [showTime]="true"
            dateFormat="yy-mm-dd"
            hourFormat="24"
            placeholder="Start date"
            [showButtonBar]="true"
            class="w-full"/>
        </div>
        <div>
          <label class="block text-xs text-surface-500 mb-1">To</label>
          <p-datepicker
            [ngModel]="endDate()"
            (ngModelChange)="onEndDateChange($event)"
            [showTime]="true"
            dateFormat="yy-mm-dd"
            hourFormat="24"
            placeholder="End date"
            [showButtonBar]="true"
            class="w-full"/>
        </div>
      </div>

      <!-- Bottom row: Quick presets + Clear + Count -->
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <p-selectButton
            [ngModel]="activePreset()"
            (ngModelChange)="onPresetChange($event)"
            [options]="presetOptions"
            optionLabel="label"
            optionValue="value"
            [allowEmpty]="true"
            size="small"/>
        </div>
        <div class="flex items-center gap-3">
          @if (hasActiveFilters()) {
            <p-button label="Clear" severity="secondary" [outlined]="true" size="small" (onClick)="clearFilters()"/>
          }
          <span class="text-xs text-surface-500 whitespace-nowrap">{{ totalRuns() }} runs</span>
        </div>
      </div>
    </div>
  `,
})
export class RunFilterPanelComponent {
  totalRuns = input(0);
  filterChange = output<RunFilter>();

  status = signal<string | null>(null);
  startDate = signal<Date | null>(null);
  endDate = signal<Date | null>(null);
  activePreset = signal<string | null>(null);

  statusOptions = [
    { label: 'Completed', value: 'COMPLETED' },
    { label: 'Failed', value: 'FAILED' },
    { label: 'Running', value: 'RUNNING' },
    { label: 'Pending', value: 'PENDING' },
  ];

  presetOptions = [
    { label: 'Last 1h', value: '1h' },
    { label: 'Last 24h', value: '24h' },
    { label: 'Last 7d', value: '7d' },
    { label: 'Last 30d', value: '30d' },
  ];

  hasActiveFilters(): boolean {
    return this.status() !== null || this.startDate() !== null || this.endDate() !== null || this.activePreset() !== null;
  }

  onStatusChange(value: string | null): void {
    this.status.set(value);
    this.emitFilter();
  }

  onStartDateChange(date: Date | null): void {
    this.startDate.set(date);
    this.activePreset.set(null);
    this.emitFilter();
  }

  onEndDateChange(date: Date | null): void {
    this.endDate.set(date);
    this.activePreset.set(null);
    this.emitFilter();
  }

  onPresetChange(value: string | null): void {
    this.activePreset.set(value);
    if (value && PRESET_MS[value]) {
      this.startDate.set(new Date(Date.now() - PRESET_MS[value]));
      this.endDate.set(null);
    } else {
      this.startDate.set(null);
      this.endDate.set(null);
    }
    this.emitFilter();
  }

  clearFilters(): void {
    this.status.set(null);
    this.startDate.set(null);
    this.endDate.set(null);
    this.activePreset.set(null);
    this.emitFilter();
  }

  private emitFilter(): void {
    const f: RunFilter = {};
    if (this.status()) f.status = this.status()!;
    if (this.startDate()) f.started_after = this.startDate()!.toISOString();
    if (this.endDate()) f.started_before = this.endDate()!.toISOString();
    this.filterChange.emit(f);
  }
}
