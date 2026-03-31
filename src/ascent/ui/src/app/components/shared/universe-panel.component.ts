import { Component, computed, EventEmitter, inject, input, OnInit, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { Instrument, UniverseItem } from '../../models/asset.model';
import { TableModule } from 'primeng/table';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { UniverseTableComponent } from './universe-table.component';

@Component({
  selector: 'app-universe-panel',
  standalone: true,
  imports: [
    FormsModule,
    TableModule,
    InputText,
    Select,
    Button,
    Tag,
    Card,
    UniverseTableComponent,
  ],
  template: `
    <div class="overflow-y-auto h-full p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-semibold text-sm">Instrument Universe</h3>
          <p class="text-xs text-surface-400 mt-1">{{ subtitle() }}</p>
        </div>
        @if (!showForm()) {
          <p-button label="+ Add Instruments" [outlined]="true" size="small" (onClick)="openForm()"/>
        }
      </div>

      <!-- Add Instruments Form -->
      @if (showForm()) {
        <p-card styleClass="mb-6">
          <ng-template #header>
            <div class="flex items-center justify-between px-5 pt-4">
              <div>
                <span class="font-semibold text-sm">Select Instruments</span>
                <span class="text-xs text-surface-400 ml-2">{{ stagedIds().size }} staged</span>
              </div>
              <div class="flex items-center gap-2">
                <p-button label="Cancel" severity="secondary" [text]="true" size="small" (onClick)="cancelForm()"/>
                <p-button
                  [label]="'Add ' + stagedIds().size + ' Instrument' + (stagedIds().size === 1 ? '' : 's')"
                  size="small"
                  (onClick)="submitStaged()"
                  [disabled]="stagedIds().size === 0"/>
              </div>
            </div>
          </ng-template>

          <!-- Available instruments table -->
          <p-table
            #dt
            [value]="availableInstruments()"
            [paginator]="true"
            [rows]="10"
            [rowsPerPageOptions]="[10, 25, 50]"
            [showCurrentPageReport]="true"
            currentPageReportTemplate="{first}–{last} of {totalRecords}"
            [tableStyle]="{'width': '100%'}"
            [globalFilterFields]="['name', 'display_name']"
            dataKey="id">
            <ng-template #caption>
              <div class="flex items-center justify-between gap-4">
                <div class="flex items-center gap-2 flex-1">
                  <input type="text" pInputText placeholder="Search instruments..." (input)="dt.filterGlobal($any($event.target).value, 'contains')" class="w-64"/>
                  <p-select
                    [(ngModel)]="typeFilter"
                    [options]="typeFilterOptions()"
                    optionLabel="label"
                    optionValue="value"
                    placeholder="All Types"
                    [showClear]="true"
                    (onChange)="onTypeFilter($event.value, dt)"
                    appendTo="body"/>
                  <p-select
                    [(ngModel)]="statusFilter"
                    [options]="statusFilterOptions"
                    optionLabel="label"
                    optionValue="value"
                    placeholder="All Statuses"
                    [showClear]="true"
                    (onChange)="onStatusFilter($event.value, dt)"
                    appendTo="body"/>
                </div>
                <p-button
                  label="Stage All Filtered"
                  severity="secondary"
                  [outlined]="true"
                  size="small"
                  (onClick)="stageAllFiltered(dt)"/>
              </div>
            </ng-template>
            <ng-template #header>
              <tr>
                <th pSortableColumn="display_name">Display Name <p-sortIcon field="display_name"/></th>
                <th pSortableColumn="name">Name <p-sortIcon field="name"/></th>
                <th>Type</th>
                <th>Pair</th>
                <th pSortableColumn="is_active" class="w-24">Status <p-sortIcon field="is_active"/></th>
                <th class="w-20"></th>
              </tr>
            </ng-template>
            <ng-template #body let-inst>
              <tr [class.bg-green-500/5]="stagedIds().has(inst.id)">
                <td class="font-medium">{{ inst.display_name }}</td>
                <td class="font-mono text-surface-500 text-xs">{{ inst.name }}</td>
                <td class="text-xs">{{ getTypeName(inst.instrument_type_id) }}</td>
                <td class="font-mono text-surface-500 text-xs text-center">{{ inst.from_asset_name }}/{{ inst.to_asset_name }}</td>
                <td>
                  <p-tag [value]="inst.is_active ? 'Active' : 'Inactive'" [severity]="inst.is_active ? 'success' : 'secondary'" [rounded]="true"/>
                </td>
                <td>
                  @if (stagedIds().has(inst.id)) {
                    <p-button label="Staged" severity="success" [text]="true" size="small" (onClick)="unstage(inst.id)"/>
                  } @else {
                    <p-button label="Add" severity="info" [text]="true" size="small" (onClick)="stage(inst.id)"/>
                  }
                </td>
              </tr>
            </ng-template>
            <ng-template #emptymessage>
              <tr>
                <td colspan="6" class="text-center text-surface-400 py-6">
                  @if (assetService.instruments().length === 0) {
                    No instruments available. Create instruments first.
                  } @else {
                    All instruments are already in the universe.
                  }
                </td>
              </tr>
            </ng-template>
          </p-table>
        </p-card>
      }

      <!-- Universe Table -->
      <app-universe-table [items]="items()" (remove)="remove.emit($event)"/>
    </div>
  `,
})
export class UniversePanelComponent implements OnInit {
  assetService = inject(AssetService);

  ngOnInit(): void {
    this.assetService.loadInstruments();
    this.assetService.loadInstrumentTypes();
  }

  items = input<UniverseItem[]>([]);
  subtitle = input('Instruments in this universe.');
  @Output() addInstruments = new EventEmitter<{ instrumentIds: string[]; startOrder: number }>();
  @Output() remove = new EventEmitter<string>();

  showForm = signal(false);
  stagedIds = signal<Set<string>>(new Set());

  // Filters
  typeFilter = '';
  statusFilter: boolean | '' = '';

  statusFilterOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  /** Instruments not already in the universe. */
  availableInstruments = computed(() => {
    const existingIds = new Set(this.items().map(i => i.instrument_id));
    return this.assetService.instruments().filter(i => !existingIds.has(i.id));
  });

  typeFilterOptions = computed(() => {
    const types = this.assetService.instrumentTypes();
    return types.map(t => ({ label: t.display_name || t.name, value: t.id }));
  });

  getTypeName(typeId: string): string {
    return this.assetService.instrumentTypes().find(t => t.id === typeId)?.name ?? '';
  }

  openForm(): void {
    this.stagedIds.set(new Set());
    this.typeFilter = '';
    this.statusFilter = '';
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }

  stage(id: string): void {
    this.stagedIds.update(s => { const n = new Set(s); n.add(id); return n; });
  }

  unstage(id: string): void {
    this.stagedIds.update(s => { const n = new Set(s); n.delete(id); return n; });
  }

  stageAllFiltered(dt: any): void {
    const filtered: Instrument[] = dt.filteredValue ?? this.availableInstruments();
    this.stagedIds.update(s => {
      const n = new Set(s);
      for (const inst of filtered) n.add(inst.id);
      return n;
    });
  }

  onTypeFilter(value: string | null, dt: any): void {
    dt.filter(value, 'instrument_type_id', 'equals');
  }

  onStatusFilter(value: boolean | null, dt: any): void {
    dt.filter(value, 'is_active', 'equals');
  }

  submitStaged(): void {
    const ids = Array.from(this.stagedIds());
    if (ids.length === 0) return;
    this.addInstruments.emit({ instrumentIds: ids, startOrder: this.items().length + 1 });
    this.showForm.set(false);
    this.stagedIds.set(new Set());
  }
}
