import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { RunDetailCardComponent, RunDetailField } from '../../shared/run-detail-card.component';
import { PartitionDataTableComponent } from '../../shared/partition-data-table.component';
import { EmptyStateComponent } from '../../shared/empty-state.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-feed-run-detail',
  standalone: true,
  imports: [
    RouterLink,
    Tabs, TabList, Tab,
    Tag,
    Skeleton,
    RunDetailCardComponent,
    PartitionDataTableComponent,
    EmptyStateComponent,
  ],
  templateUrl: './feed-run-detail.component.html',
})
export class FeedRunDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private feedService = inject(FeedService);

  feedId = '';
  runId = '';

  run = signal<FeedRunListItem | null>(null);
  loading = signal(true);
  activeTab = signal('Overview');

  // Partition data state
  partitionData = signal<Record<string, any>[]>([]);
  partitionTotal = signal(0);
  partitionPage = signal(1);
  partitionPageSize = signal(25);
  partitionTotalPages = signal(0);
  partitionLoading = signal(false);

  extraFields: RunDetailField[] = [
    { label: 'Records Fetched', key: 'records_fetched' },
    { label: 'Partition Key', key: 'partition_key' },
  ];

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.feedId = params.get('id')!;
      this.runId = params.get('runId')!;

      this.loading.set(true);
      this.run.set(null);

      this.feedService.loadFeedDetail(this.feedId);

      this.feedService.getFeedRun(this.feedId, this.runId).subscribe({
        next: run => {
          this.run.set(run);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    });
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    if (tab === 'Partition' && this.partitionData().length === 0) {
      this.loadPartitionData();
    }
  }

  loadPartitionData(): void {
    const r = this.run();
    if (!r?.partition_id) return;
    this.partitionLoading.set(true);
    this.feedService.loadPartitionData(this.feedId, r.partition_id, this.partitionPage(), this.partitionPageSize()).subscribe({
      next: res => {
        this.partitionData.set(res.items);
        this.partitionTotal.set(res.total);
        this.partitionTotalPages.set(res.total_pages);
        this.partitionLoading.set(false);
      },
      error: () => this.partitionLoading.set(false),
    });
  }

  onPartitionPageChange(page: number): void {
    this.partitionPage.set(page);
    this.loadPartitionData();
  }

  onPartitionPageSizeChange(size: number): void {
    this.partitionPageSize.set(size);
    this.partitionPage.set(1);
    this.loadPartitionData();
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
}
