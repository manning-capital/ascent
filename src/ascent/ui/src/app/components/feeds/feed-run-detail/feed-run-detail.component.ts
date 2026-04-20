import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';
import { FeedService } from '../../../services/feed.service';
import { FeedRunListItem, FeedRunTradeItem } from '../../../models/feed.model';
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

  // "Partition" kept as a query-string alias for backwards-compat with
  // bookmarked URLs — resolves to the Data tab in code.
  private tabAliases: Record<string, string> = { Partition: 'Data' };
  tabs = ['Overview', 'Data', 'Trades'];

  feedId = '';
  runId = '';

  run = signal<FeedRunListItem | null>(null);
  trades = signal<FeedRunTradeItem[]>([]);
  tradesLoading = signal(false);
  loading = signal(true);
  activeTab = signal('Overview');

  // Run data via infinite row model — joins on run.snapshot_timestamp
  runDataFetchPage = computed<ServerFetchFn<Record<string, any>> | null>(() => {
    const r = this.run();
    if (!r) return null;
    const feedId = this.feedId;
    const runId = this.runId;
    return (page: number, pageSize: number, _sort?: { field: string; order: string }) =>
      this.feedService.loadRunData(feedId, runId, page, pageSize).pipe(
        map(res => ({ items: res.items, total: res.total })),
      );
  });

  extraFields: RunDetailField[] = [
    { label: 'Records Fetched', key: 'records_fetched' },
    { label: 'Snapshot Timestamp', key: 'snapshot_timestamp' },
  ];

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.feedId = params.get('id')!;
      this.runId = params.get('runId')!;

      const qp = this.route.snapshot.queryParamMap;
      const rawTab = qp.get('tab');
      const tab = rawTab && this.tabAliases[rawTab] ? this.tabAliases[rawTab] : rawTab;
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Overview');
      }

      this.loading.set(true);
      this.run.set(null);
      this.trades.set([]);

      this.feedService.loadFeedDetail(this.feedId);

      this.feedService.getFeedRun(this.feedId, this.runId).subscribe({
        next: run => {
          this.run.set(run);
          this.loading.set(false);
          if (this.activeTab() === 'Trades') {
            this.loadTrades();
          }
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
    if (tab === 'Trades' && this.trades().length === 0) {
      this.loadTrades();
    }
  }

  loadTrades(): void {
    this.tradesLoading.set(true);
    this.feedService.loadRunTrades(this.feedId, this.runId).subscribe({
      next: trades => {
        this.trades.set(trades);
        this.tradesLoading.set(false);
      },
      error: () => this.tradesLoading.set(false),
    });
  }

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED':
      case 'OPEN':
      case 'CLOSED': return 'success';
      case 'FAILED':
      case 'ERROR': return 'danger';
      case 'RUNNING':
      case 'OPENING':
      case 'CLOSING': return 'warn';
      case 'PENDING':
      case 'WAITING': return 'secondary';
      default: return 'secondary';
    }
  }
}
