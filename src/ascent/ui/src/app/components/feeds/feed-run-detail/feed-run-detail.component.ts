import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem } from '../../../models/feed.model';
import type { ServerFetchFn } from '../../shared/data-table/data-table.model';
import { RunDetailCardComponent, RunDetailField } from '../../shared/run-detail-card.component';
import { ServerTableComponent } from '../../shared/data-table/server-table.component';
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
    ServerTableComponent,
    EmptyStateComponent,
  ],
  templateUrl: './feed-run-detail.component.html',
})
export class FeedRunDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private feedService = inject(FeedService);

  tabs = ['Overview', 'Partition'];

  feedId = '';
  runId = '';

  run = signal<FeedRunListItem | null>(null);
  loading = signal(true);
  activeTab = signal('Overview');

  // Partition data via infinite row model
  partitionFetchPage = computed<ServerFetchFn<Record<string, any>> | null>(() => {
    const r = this.run();
    if (!r?.partition_id) return null;
    const feedId = this.feedId;
    const partitionId = r.partition_id;
    return (page: number, pageSize: number) =>
      this.feedService.loadPartitionData(feedId, partitionId, page, pageSize).pipe(
        map(res => ({ items: res.items, total: res.total })),
      );
  });

  extraFields: RunDetailField[] = [
    { label: 'Records Fetched', key: 'records_fetched' },
    { label: 'Partition Key', key: 'partition_key' },
  ];

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.feedId = params.get('id')!;
      this.runId = params.get('runId')!;

      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Overview');
      }

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
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
    // Partition tab data loads automatically via infinite row model
  }

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'secondary';
    }
  }
}
