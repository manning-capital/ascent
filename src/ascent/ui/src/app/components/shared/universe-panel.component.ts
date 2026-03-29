import { Component, computed, EventEmitter, inject, Input, OnInit, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { UniverseItem, UniverseItemCreate, AssetGroup, AssetGroupCreate, AssetGroupMemberCreate } from '../../models/asset.model';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { UniverseTableComponent } from './universe-table.component';

interface PairEntry {
  providerId: string;
  fromAssetId: string;
  toAssetId: string;
}

@Component({
  selector: 'app-universe-panel',
  standalone: true,
  imports: [
    FormsModule,
    DragDropModule,
    Select,
    SelectButton,
    Button,
    Card,
    UniverseTableComponent,
  ],
  styles: [`
    .pair-row {
      background: var(--p-content-hover-background);
    }
    .cdk-drag-preview {
      background: var(--p-content-hover-background);
      border: 1px solid var(--p-content-border-color);
      border-radius: 0.5rem;
      padding: 0.5rem;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }
    .cdk-drag-placeholder {
      opacity: 0.3;
    }
    .cdk-drag-animating {
      transition: transform 200ms ease;
    }
    .cdk-drop-list-dragging .pair-row:not(.cdk-drag-placeholder) {
      transition: transform 200ms ease;
    }
    .drag-handle {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 1.5rem;
      height: 100%;
      min-height: 2rem;
      cursor: grab;
      touch-action: none;
    }
    .drag-handle:active {
      cursor: grabbing;
    }
  `],
  template: `
    <div class="overflow-y-auto h-full p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-semibold text-sm">Asset Universe</h3>
          <p class="text-xs text-surface-400 mt-1">{{ subtitle }}</p>
        </div>
        <p-button label="+ Add" [outlined]="true" size="small" (onClick)="openForm()"/>
      </div>

      <!-- Add Form -->
      @if (showForm()) {
        <p-card class="mb-6">
          <ng-template #header>
            <div class="flex items-center justify-between px-5 pt-4">
              <span class="font-semibold text-sm">Add to Universe</span>
              <p-button label="&times;" severity="secondary" [text]="true" [rounded]="true" size="small" (onClick)="cancelForm()"/>
            </div>
          </ng-template>

          <!-- Mode Toggle -->
          <p-selectButton
            [options]="addModeOptions"
            [ngModel]="addMode()"
            (ngModelChange)="addMode.set($event)"
            optionLabel="label"
            optionValue="value"
            size="small"
            class="mb-4"/>

          @if (addMode() === 'individual') {
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-xs font-medium text-muted-color mb-1">Provider</label>
                <p-select [(ngModel)]="providerId" [options]="providerService.providers()" optionLabel="name" optionValue="id" placeholder="Select provider" [showClear]="true" [fluid]="true" appendTo="body"/>
              </div>
              <div>
                <label class="block text-xs font-medium text-muted-color mb-1">From Asset (Base)</label>
                <p-select [(ngModel)]="fromAssetId" [options]="assetOptions()" optionLabel="displayLabel" optionValue="id" placeholder="Select base asset" [showClear]="true" [filter]="true" [fluid]="true" appendTo="body"/>
              </div>
              <div>
                <label class="block text-xs font-medium text-muted-color mb-1">To Asset (Quote)</label>
                <p-select [(ngModel)]="toAssetId" [options]="assetOptions()" optionLabel="displayLabel" optionValue="id" placeholder="Select quote asset" [showClear]="true" [filter]="true" [fluid]="true" appendTo="body"/>
              </div>
            </div>
            <div class="flex justify-end gap-2 mt-4">
              <p-button label="Cancel" severity="secondary" [outlined]="true" size="small" (onClick)="cancelForm()"/>
              <p-button label="Add Pair" size="small" (onClick)="submitItem()"/>
            </div>
          }

          @if (addMode() === 'multiple') {
            <!-- Column headers -->
            <div class="grid gap-4 mb-2" style="grid-template-columns: 1.5rem 1fr 1fr 1fr 1.5rem;">
              <div></div>
              <label class="block text-xs font-medium text-muted-color">Provider</label>
              <label class="block text-xs font-medium text-muted-color">From Asset (Base)</label>
              <label class="block text-xs font-medium text-muted-color">To Asset (Quote)</label>
              <div></div>
            </div>

            <!-- Draggable pair rows -->
            <div cdkDropList (cdkDropListDropped)="onPairDrop($event)" class="space-y-2">
              @for (pair of multiPairs(); track $index) {
                <div cdkDrag class="pair-row grid gap-4 items-center rounded-lg border border-surface p-2" style="grid-template-columns: 1.5rem 1fr 1fr 1fr 1.5rem;">
                  <div cdkDragHandle class="drag-handle" title="Drag to reorder">
                    <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor" class="text-muted-color">
                      <circle cx="2" cy="2" r="1.5"/><circle cx="8" cy="2" r="1.5"/>
                      <circle cx="2" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/>
                      <circle cx="2" cy="14" r="1.5"/><circle cx="8" cy="14" r="1.5"/>
                    </svg>
                  </div>
                  <p-select [(ngModel)]="pair.providerId" [options]="providerService.providers()" optionLabel="name" optionValue="id" placeholder="Provider" [showClear]="true" [fluid]="true" appendTo="body" size="small"/>
                  <p-select [(ngModel)]="pair.fromAssetId" [options]="assetOptions()" optionLabel="displayLabel" optionValue="id" placeholder="Base asset" [showClear]="true" [filter]="true" [fluid]="true" appendTo="body" size="small"/>
                  <p-select [(ngModel)]="pair.toAssetId" [options]="assetOptions()" optionLabel="displayLabel" optionValue="id" placeholder="Quote asset" [showClear]="true" [filter]="true" [fluid]="true" appendTo="body" size="small"/>
                  @if (multiPairs().length > 2) {
                    <button type="button" class="text-surface-400 hover:text-red-500 transition-colors text-xs" (click)="removeMultiPair($index)">
                      <i class="pi pi-times"></i>
                    </button>
                  } @else {
                    <div></div>
                  }
                </div>
              }
            </div>

            <!-- Add another pair button -->
            <button type="button" (click)="addMultiPair()" class="mt-2 flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors py-1.5">
              <i class="pi pi-plus text-xs"></i>
              <span>Add another pair</span>
            </button>

            <div class="flex justify-end gap-2 mt-4">
              <p-button label="Cancel" severity="secondary" [outlined]="true" size="small" (onClick)="cancelForm()"/>
              <p-button label="Create Group & Add" size="small" (onClick)="submitMultiple()" [disabled]="!isMultiValid"/>
            </div>
          }
        </p-card>
      }

      <!-- Universe Table -->
      <app-universe-table [items]="items" (remove)="remove.emit($event)" (removeGroup)="removeGroup.emit($event)"/>
    </div>
  `,
})
export class UniversePanelComponent implements OnInit {
  assetService = inject(AssetService);
  providerService = inject(ProviderService);

  ngOnInit(): void {
    this.assetService.loadAssets();
    this.assetService.loadAssetGroups({ min_members: '2' });
    this.providerService.loadProviders();
  }

  @Input() items: UniverseItem[] = [];
  @Input() subtitle = 'Asset groups and individual pairs.';
  @Output() addItem = new EventEmitter<UniverseItemCreate>();
  @Output() createGroupAndAdd = new EventEmitter<{ members: AssetGroupMemberCreate[]; startOrder: number }>();
  @Output() remove = new EventEmitter<UniverseItem>();
  @Output() removeGroup = new EventEmitter<UniverseItem[]>();

  showForm = signal(false);
  addMode = signal<'individual' | 'multiple'>('individual');
  providerId = '';
  fromAssetId = '';
  toAssetId = '';

  // Multiple pairs state
  multiPairs = signal<PairEntry[]>([]);

  addModeOptions = [
    { label: 'Individual Pair', value: 'individual' },
    { label: 'Grouped Pairs', value: 'multiple' },
  ];

  assetOptions = computed(() =>
    this.assetService.assets().map(a => ({ id: a.id, displayLabel: a.symbol || a.name }))
  );

  get isMultiValid(): boolean {
    const pairs = this.multiPairs();
    return pairs.length >= 2 && pairs.every(p => p.providerId && p.fromAssetId && p.toAssetId);
  }

  openForm(): void {
    this.providerId = this.providerService.providers()[0]?.id ?? '';
    this.fromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.toAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.addMode.set('individual');
    this.resetMultiPairs();
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
  }

  // --- Individual pair ---

  submitItem(): void {
    if (!this.providerId || !this.fromAssetId || !this.toAssetId) return;
    const data: UniverseItemCreate = {
      provider_id: this.providerId,
      from_asset_id: this.fromAssetId,
      to_asset_id: this.toAssetId,
      order: this.items.length + 1,
    };
    this.addItem.emit(data);
    this.showForm.set(false);
  }

  // --- Multiple pairs ---

  private resetMultiPairs(): void {
    const defaultProvider = this.providerService.providers()[0]?.id ?? '';
    this.multiPairs.set([
      { providerId: defaultProvider, fromAssetId: '', toAssetId: '' },
      { providerId: defaultProvider, fromAssetId: '', toAssetId: '' },
    ]);
  }

  addMultiPair(): void {
    const defaultProvider = this.providerService.providers()[0]?.id ?? '';
    this.multiPairs.update(pairs => [...pairs, { providerId: defaultProvider, fromAssetId: '', toAssetId: '' }]);
  }

  removeMultiPair(index: number): void {
    this.multiPairs.update(pairs => pairs.filter((_, i) => i !== index));
  }

  onPairDrop(event: CdkDragDrop<PairEntry[]>): void {
    const pairs = [...this.multiPairs()];
    moveItemInArray(pairs, event.previousIndex, event.currentIndex);
    this.multiPairs.set(pairs);
  }

  submitMultiple(): void {
    const pairs = this.multiPairs();
    if (pairs.length < 2 || !pairs.every(p => p.providerId && p.fromAssetId && p.toAssetId)) return;
    const members: AssetGroupMemberCreate[] = pairs.map((p, i) => ({
      provider_id: p.providerId,
      from_asset_id: p.fromAssetId,
      to_asset_id: p.toAssetId,
      order: i + 1,
    }));
    this.createGroupAndAdd.emit({ members, startOrder: this.items.length + 1 });
    this.showForm.set(false);
  }
}
