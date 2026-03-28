import { Component, computed, EventEmitter, inject, Input, OnInit, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { UniverseItem, UniverseItemCreate, AssetGroup } from '../../models/asset.model';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { UniverseTableComponent } from './universe-table.component';

@Component({
  selector: 'app-universe-panel',
  standalone: true,
  imports: [
    FormsModule,
    Select,
    SelectButton,
    Button,
    Tag,
    Card,
    UniverseTableComponent,
  ],
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

          @if (addMode() === 'group') {
            <div>
              <label class="block text-xs font-medium text-muted-color mb-1">Asset Group</label>
              <p-select [(ngModel)]="groupId" [options]="groupOptions()" optionValue="id" placeholder="Search groups..." [showClear]="true" [filter]="true" filterBy="displayLabel" [fluid]="true" appendTo="body">
                <ng-template #selectedItem let-group>
                  <span class="text-sm">{{ group.displayLabel }}</span>
                </ng-template>
                <ng-template #item let-group>
                  <div class="py-1">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="text-xs font-medium text-muted-color">{{ group.members.length }} pair{{ group.members.length !== 1 ? 's' : '' }}</span>
                      @if (!group.is_active) {
                        <p-tag value="Inactive" severity="secondary" [rounded]="true"/>
                      }
                    </div>
                    <div class="flex flex-wrap gap-1">
                      @for (m of group.members; track m.order) {
                        <span class="text-xs font-mono bg-emphasis rounded px-1.5 py-0.5">{{ m.from_asset_symbol }}/{{ m.to_asset_symbol }}</span>
                      }
                    </div>
                    @if (group.members.length > 0) {
                      <div class="text-xs text-muted-color mt-1">via {{ group.members[0].provider_name }}</div>
                    }
                  </div>
                </ng-template>
              </p-select>
            </div>
            <div class="flex justify-end gap-2 mt-4">
              <p-button label="Cancel" severity="secondary" [outlined]="true" size="small" (onClick)="cancelForm()"/>
              <p-button label="Link Group" size="small" (onClick)="submitGroup()"/>
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
  @Output() addAssetGroup = new EventEmitter<{ group: AssetGroup; startOrder: number }>();
  @Output() remove = new EventEmitter<UniverseItem>();
  @Output() removeGroup = new EventEmitter<UniverseItem[]>();

  showForm = signal(false);
  addMode = signal<'individual' | 'group'>('individual');
  providerId = '';
  fromAssetId = '';
  toAssetId = '';
  groupId = '';

  addModeOptions = [
    { label: 'Individual Pair', value: 'individual' },
    { label: 'Asset Group', value: 'group' },
  ];

  assetOptions = computed(() =>
    this.assetService.assets().map(a => ({ id: a.id, displayLabel: a.symbol || a.name }))
  );

  groupOptions = computed(() =>
    this.assetService.assetGroups()
      .filter(g => g.members.length >= 2)
      .map(g => ({
        ...g,
        displayLabel: g.members.map(m => `${m.from_asset_symbol}/${m.to_asset_symbol}`).join(', ') || 'Empty group',
      }))
  );

  openForm(): void {
    this.providerId = this.providerService.providers()[0]?.id ?? '';
    this.fromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.toAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.groupId = '';
    this.addMode.set('individual');
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
  }

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

  submitGroup(): void {
    if (!this.groupId) return;
    const group = this.assetService.assetGroups().find(g => g.id === this.groupId);
    if (!group || group.members.length === 0) return;
    this.addAssetGroup.emit({ group, startOrder: this.items.length + 1 });
    this.showForm.set(false);
  }
}
