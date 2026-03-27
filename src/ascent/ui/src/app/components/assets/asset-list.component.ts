import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../services/asset.service';
import { ProviderService } from '../../services/provider.service';
import { ToastService } from '../../services/toast.service';
import { LoadingSpinnerComponent } from '../shared/loading-spinner.component';
import {
  AssetListItem, AssetCreate,
  ProviderAssetLink, ProviderAssetLinkCreate,
  AssetGroup, AssetGroupCreate, AssetGroupMemberCreate,
} from '../../models/asset.model';

type Tab = 'assets' | 'mappings' | 'groups';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [RouterLink, FormsModule, LoadingSpinnerComponent],
  templateUrl: './asset-list.component.html',
})
export class AssetListComponent implements OnInit {
  assetService = inject(AssetService);
  providerService = inject(ProviderService);
  private toast = inject(ToastService);

  activeTab = signal<Tab>('assets');
  search = signal('');
  selectedTypeId = signal<string | null>(null);

  // Asset create
  showAssetForm = signal(false);
  newAssetName = '';
  newAssetSymbol = '';
  newAssetDescription = '';
  newAssetTypeId = '';

  // Provider-asset link create
  showLinkForm = signal(false);
  newLinkProviderId = '';
  newLinkAssetId = '';
  newLinkIdentifier = '';

  // Asset group create
  showGroupForm = signal(false);
  newGroupMembers: AssetGroupMemberCreate[] = [];
  // Temp member fields
  tmpMemberProviderId = '';
  tmpMemberFromAssetId = '';
  tmpMemberToAssetId = '';

  ngOnInit(): void {
    this.assetService.loadAssets();
    this.assetService.loadAssetTypes();
    this.assetService.loadProviderAssetLinks();
    this.assetService.loadAssetGroups();
    this.providerService.loadProviders();
  }

  setTab(tab: Tab): void {
    this.activeTab.set(tab);
  }

  // ---- Assets ----

  setTypeFilter(typeId: string | null): void {
    this.selectedTypeId.set(typeId);
  }

  filteredAssets(): AssetListItem[] {
    let items = this.assetService.assets();
    const typeId = this.selectedTypeId();
    if (typeId) {
      items = items.filter(a => a.asset_type_id === typeId);
    }
    const term = this.search().toLowerCase();
    if (!term) return items;
    return items.filter(a =>
      a.name.toLowerCase().includes(term) ||
      (a.symbol?.toLowerCase().includes(term)) ||
      (a.asset_type_name?.toLowerCase().includes(term))
    );
  }

  openAssetCreate(): void {
    this.newAssetName = '';
    this.newAssetSymbol = '';
    this.newAssetDescription = '';
    this.newAssetTypeId = this.assetService.assetTypes()[0]?.id ?? '';
    this.showAssetForm.set(true);
  }

  cancelAssetCreate(): void {
    this.showAssetForm.set(false);
  }

  submitAssetCreate(): void {
    if (!this.newAssetName.trim() || !this.newAssetTypeId) return;
    const data: AssetCreate = {
      asset_type_id: this.newAssetTypeId,
      name: this.newAssetName.trim(),
      symbol: this.newAssetSymbol.trim() || null,
      description: this.newAssetDescription.trim() || null,
    };
    this.assetService.createAsset(data).subscribe({
      next: () => {
        this.toast.success('Asset created');
        this.showAssetForm.set(false);
        this.assetService.loadAssets();
      },
      error: () => this.toast.error('Failed to create asset'),
    });
  }

  // ---- Provider-Asset Links ----

  filteredLinks(): ProviderAssetLink[] {
    const term = this.search().toLowerCase();
    if (!term) return this.assetService.providerAssetLinks();
    return this.assetService.providerAssetLinks().filter(l =>
      (l.provider_name?.toLowerCase().includes(term)) ||
      (l.asset_name?.toLowerCase().includes(term)) ||
      l.identifier.toLowerCase().includes(term)
    );
  }

  openLinkCreate(): void {
    this.newLinkProviderId = this.providerService.providers()[0]?.id ?? '';
    this.newLinkAssetId = this.assetService.assets()[0]?.id ?? '';
    this.newLinkIdentifier = '';
    this.showLinkForm.set(true);
  }

  cancelLinkCreate(): void {
    this.showLinkForm.set(false);
  }

  submitLinkCreate(): void {
    if (!this.newLinkProviderId || !this.newLinkAssetId || !this.newLinkIdentifier.trim()) return;
    const data: ProviderAssetLinkCreate = {
      provider_id: this.newLinkProviderId,
      asset_id: this.newLinkAssetId,
      identifier: this.newLinkIdentifier.trim(),
    };
    this.assetService.createProviderAssetLink(data).subscribe({
      next: () => {
        this.toast.success('Provider-asset mapping created');
        this.showLinkForm.set(false);
        this.assetService.loadProviderAssetLinks();
      },
      error: () => this.toast.error('Failed to create mapping'),
    });
  }

  deleteLink(link: ProviderAssetLink): void {
    this.assetService.deleteProviderAssetLink(link.provider_id, link.asset_id).subscribe({
      next: () => {
        this.toast.success('Mapping removed');
        this.assetService.loadProviderAssetLinks();
      },
      error: () => this.toast.error('Failed to remove mapping'),
    });
  }

  // ---- Asset Groups ----

  openGroupCreate(): void {
    this.newGroupMembers = [];
    this.tmpMemberProviderId = this.providerService.providers()[0]?.id ?? '';
    this.tmpMemberFromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.tmpMemberToAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.showGroupForm.set(true);
  }

  cancelGroupCreate(): void {
    this.showGroupForm.set(false);
  }

  addTempMember(): void {
    if (!this.tmpMemberProviderId || !this.tmpMemberFromAssetId || !this.tmpMemberToAssetId) return;
    this.newGroupMembers = [...this.newGroupMembers, {
      provider_id: this.tmpMemberProviderId,
      from_asset_id: this.tmpMemberFromAssetId,
      to_asset_id: this.tmpMemberToAssetId,
      order: this.newGroupMembers.length + 1,
    }];
  }

  removeTempMember(index: number): void {
    this.newGroupMembers = this.newGroupMembers.filter((_, i) => i !== index).map((m, i) => ({ ...m, order: i + 1 }));
  }

  submitGroupCreate(): void {
    if (this.newGroupMembers.length === 0) return;
    const data: AssetGroupCreate = {
      members: this.newGroupMembers,
    };
    this.assetService.createAssetGroup(data).subscribe({
      next: () => {
        this.toast.success('Asset group created');
        this.showGroupForm.set(false);
        this.assetService.loadAssetGroups();
      },
      error: () => this.toast.error('Failed to create group'),
    });
  }

  deleteGroup(group: AssetGroup): void {
    this.assetService.deleteAssetGroup(group.id).subscribe({
      next: () => {
        this.toast.success('Group deleted');
        this.assetService.loadAssetGroups();
      },
      error: () => this.toast.error('Failed to delete group'),
    });
  }

  assetName(id: string): string {
    const a = this.assetService.assets().find(a => a.id === id);
    return a?.symbol || a?.name || id.substring(0, 8);
  }

  providerName(id: string): string {
    const p = this.providerService.providers().find(p => p.id === id);
    return p?.name || id.substring(0, 8);
  }
}
