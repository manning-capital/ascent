import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FeedService } from '../../../services/feed.service';
import { ToastService } from '../../../services/toast.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { UniverseItem } from '../../../models/asset.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { Paginator } from 'primeng/paginator';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-feed-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    TableModule,
    Tag,
    Paginator,
    Card,
    Skeleton,
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
  runsLoading = signal(false);
  skeletonRows = Array.from({ length: 8 }, (_, i) => i);

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
      },
      error: () => this.runsLoading.set(false),
    });
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

  onAddInstruments(event: { instrumentIds: string[]; startOrder: number }): void {
    this.feedService.batchAddFeedInstruments(this.feedId, event.instrumentIds, event.startOrder).subscribe({
      next: () => {
        this.toast.success(`${event.instrumentIds.length} instrument(s) added to universe`);
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to add instruments to universe'),
    });
  }

  removeUniverseItem(instrumentId: string): void {
    this.feedService.removeFeedUniverseItem(this.feedId, instrumentId).subscribe({
      next: () => {
        this.toast.success('Instrument removed from universe');
        this.loadUniverse();
      },
      error: () => this.toast.error('Failed to remove instrument'),
    });
  }
}
