import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AssetService } from '../../../services/asset.service';
import { ProviderService } from '../../../services/provider.service';
import { ToastService } from '../../../services/toast.service';
import { AssetGroup, AssetGroupMemberCreate } from '../../../models/asset.model';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Skeleton } from 'primeng/skeleton';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';

@Component({
  selector: 'app-asset-group-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    Tabs, TabList, Tab,
    Select,
    TableModule,
    Card,
    Button,
    Skeleton,
  ],
  templateUrl: './asset-group-detail.component.html',
})
export class AssetGroupDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  assetService = inject(AssetService);
  providerService = inject(ProviderService);

  tabs = ['Overview', 'Members'];
  activeTab = signal('Overview');

  groupId = '';
  group = signal<AssetGroup | null>(null);
  loading = signal(false);

  // Add member form
  showMemberForm = signal(false);
  newProviderId = '';
  newFromAssetId = '';
  newToAssetId = '';

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.groupId) return;
      this.groupId = id;

      const tab = this.route.snapshot.queryParamMap.get('tab');
      this.activeTab.set(tab && this.tabs.includes(tab) ? tab : 'Overview');
      this.showMemberForm.set(false);

      this.loadGroup();
      this.assetService.loadAssets();
      this.providerService.loadProviders();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  loadGroup(): void {
    this.loading.set(true);
    this.assetService.getAssetGroupDetail(this.groupId).subscribe({
      next: group => {
        this.group.set(group);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  openMemberForm(): void {
    this.newProviderId = this.providerService.providers()[0]?.id ?? '';
    this.newFromAssetId = this.assetService.assets()[0]?.id ?? '';
    this.newToAssetId = this.assetService.assets()[1]?.id ?? this.assetService.assets()[0]?.id ?? '';
    this.showMemberForm.set(true);
  }

  cancelMemberForm(): void {
    this.showMemberForm.set(false);
  }

  submitMember(): void {
    if (!this.newProviderId || !this.newFromAssetId || !this.newToAssetId) return;
    const g = this.group();
    const data: AssetGroupMemberCreate = {
      provider_id: this.newProviderId,
      from_asset_id: this.newFromAssetId,
      to_asset_id: this.newToAssetId,
      order: (g?.members.length ?? 0) + 1,
    };
    this.assetService.addGroupMember(this.groupId, data).subscribe({
      next: () => {
        this.toast.success('Member added');
        this.showMemberForm.set(false);
        this.loadGroup();
      },
      error: () => this.toast.error('Failed to add member'),
    });
  }

  removeMember(m: any): void {
    this.assetService.removeGroupMember(
      this.groupId, m.provider_id, m.from_asset_id, m.to_asset_id
    ).subscribe({
      next: () => {
        this.toast.success('Member removed');
        this.loadGroup();
      },
      error: () => this.toast.error('Failed to remove member'),
    });
  }
}
