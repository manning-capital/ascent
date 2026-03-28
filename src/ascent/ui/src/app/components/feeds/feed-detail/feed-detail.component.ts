import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FeedService } from '../../../services/feed.service';
import { ToastService } from '../../../services/toast.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { UniverseItem, UniverseItemCreate, AssetGroup } from '../../../models/asset.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { Splitter } from 'primeng/splitter';
import { PartitionDataTableComponent } from '../../shared/partition-data-table.component';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Paginator } from 'primeng/paginator';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../../shared/empty-state.component';

@Component({
  selector: 'app-feed-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    Splitter,
    PartitionDataTableComponent,
    TableModule,
    Tag,
    Paginator,
    Card,
    Skeleton,
    EmptyStateComponent,
    UniversePanelComponent,
  ],
  templateUrl: './feed-detail.component.html',
})
export class FeedDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  feedService = inject(FeedService);

  tabs = ['Runs', 'Universe', 'Configuration'];
  activeTab = signal('Runs');

  // Run list state
  runs = signal<FeedRunListItem[]>([]);
  totalRuns = signal(0);
  totalRunPages = signal(0);
  runPage = signal(1);
  selectedRun = signal<FeedRunListItem | null>(null);
  runsLoading = signal(false);
  skeletonRows = Array.from({ length: 8 }, (_, i) => i);

  // Partition data state
  partitionData = signal<Record<string, any>[]>([]);
  partitionDataTotal = signal(0);
  partitionDataPage = signal(1);
  partitionDataPageSize = signal(25);
  partitionDataTotalPages = signal(0);
  partitionDataLoading = signal(false);

  initialRunId: string | null = null;
  feedId = '';

  // Universe state
  universeItems = signal<UniverseItem[]>([]);

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.feedId) return;
      this.feedId = id;

      // Restore tab from query param
      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Runs');
      }
      this.runs.set([]);
      this.totalRuns.set(0);
      this.totalRunPages.set(0);
      this.runPage.set(1);
      this.selectedRun.set(null);
      this.partitionData.set([]);
      this.partitionDataTotal.set(0);
      this.partitionDataPage.set(1);
      this.partitionDataTotalPages.set(0);
      this.partitionDataLoading.set(false);
      this.initialRunId = this.route.snapshot.queryParamMap.get('run');

      this.feedService.loadFeedDetail(this.feedId);
      this.loadRuns();
      this.loadUniverse();
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.updateQueryParams({ tab });
  }

  private updateQueryParams(params: Record<string, string | null>): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: params,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  loadRuns(): void {
    this.runsLoading.set(true);
    this.feedService.loadFeedRuns(this.feedId, this.runPage(), 20).subscribe({
      next: (res) => {
        this.runs.set(res.items);
        this.totalRuns.set(res.total);
        this.totalRunPages.set(res.total_pages);
        this.runsLoading.set(false);
        if (this.initialRunId && !this.selectedRun()) {
          const match = res.items.find(r => r.id === this.initialRunId);
          if (match) this.selectRun(match);
        }
      },
      error: () => this.runsLoading.set(false),
    });
  }

  selectRun(run: FeedRunListItem): void {
    this.selectedRun.set(run);
    this.updateQueryParams({ run: run.id });
    // Load partition data if run has a partition
    if (run.partition_id) {
      this.partitionDataPage.set(1);
      this.loadPartitionData(run.partition_id);
    } else {
      this.partitionData.set([]);
      this.partitionDataTotal.set(0);
      this.partitionDataTotalPages.set(0);
    }
  }

  loadPartitionData(partitionId: string): void {
    this.partitionDataLoading.set(true);
    this.feedService.loadPartitionData(this.feedId, partitionId, this.partitionDataPage(), this.partitionDataPageSize()).subscribe({
      next: (res) => {
        this.partitionData.set(res.items);
        this.partitionDataTotal.set(res.total);
        this.partitionDataTotalPages.set(res.total_pages);
        this.partitionDataLoading.set(false);
        // Update records_fetched to match the pivoted row count the user sees
        const run = this.selectedRun();
        if (run) {
          this.selectedRun.set({ ...run, records_fetched: res.total });
        }
      },
      error: () => {
        this.partitionData.set([]);
        this.partitionDataLoading.set(false);
      },
    });
  }

  onPartitionDataPageChange(page: number): void {
    this.partitionDataPage.set(page);
    const run = this.selectedRun();
    if (run?.partition_id) {
      this.loadPartitionData(run.partition_id);
    }
  }

  onPartitionDataPageSizeChange(size: number): void {
    this.partitionDataPageSize.set(size);
    this.partitionDataPage.set(1);
  }

  onRunPageChange(page: number): void {
    this.runPage.set(page);
    this.loadRuns();
  }

  scheduleLabel(schedule: Record<string, any> | null): string {
    if (!schedule) return 'Triggered';
    const interval = schedule['interval'];
    if (!interval) return 'Triggered';
    if (interval < 60) return `Every ${interval}s`;
    if (interval < 3600) return `Every ${Math.round(interval / 60)}m`;
    if (interval < 86400) return `Every ${Math.round(interval / 3600)}h`;
    return `Every ${Math.round(interval / 86400)}d`;
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

  durationLabel(run: FeedRunListItem): string {
    if (!run.completed_at) return run.status === 'RUNNING' ? 'running...' : '-';
    const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  formatPartitionKey(key: string | null): string {
    if (!key) return '-';
    return new Date(key).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
    });
  }

  // --- Universe methods ---

  loadUniverse(): void {
    this.feedService.loadFeedUniverse(this.feedId).subscribe({
      next: items => this.universeItems.set(items),
    });
  }

  onAddUniverseItem(data: UniverseItemCreate): void {
    this.feedService.addFeedUniverseItem(this.feedId, data).subscribe({
      next: () => {
        this.toast.success('Pair added to universe');
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to add pair to universe'),
    });
  }

  onAddUniverseGroup(event: { group: AssetGroup; startOrder: number }): void {
    let completed = 0;
    const total = event.group.members.length;
    for (const member of event.group.members) {
      const data: UniverseItemCreate = {
        provider_id: member.provider_id,
        from_asset_id: member.from_asset_id,
        to_asset_id: member.to_asset_id,
        provider_asset_group_id: event.group.id,
        order: event.startOrder + member.order - 1,
      };
      this.feedService.addFeedUniverseItem(this.feedId, data).subscribe({
        next: () => {
          completed++;
          if (completed === total) {
            this.toast.success(`Asset group linked (${total} pairs)`);
            this.loadUniverse();
          }
        },
        error: () => this.toast.error('Failed to link asset group'),
      });
    }
  }

  removeUniverseItem(item: UniverseItem): void {
    this.feedService.removeFeedUniverseItem(
      this.feedId, item.provider_id, item.from_asset_id, item.to_asset_id
    ).subscribe({
      next: () => {
        this.toast.success('Pair removed from universe');
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to remove pair'),
    });
  }

  removeUniverseGroup(items: UniverseItem[]): void {
    let completed = 0;
    for (const item of items) {
      this.feedService.removeFeedUniverseItem(
        this.feedId, item.provider_id, item.from_asset_id, item.to_asset_id
      ).subscribe({
        next: () => {
          completed++;
          if (completed === items.length) {
            this.toast.success('Asset group removed from universe');
            this.loadUniverse();
          }
        },
        error: () => this.toast.error('Failed to remove asset group'),
      });
    }
  }
}
