import { Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FeedService } from '../../../services/feed.service';
import { ToastService } from '../../../services/toast.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { ImpactReport, UniverseItem } from '../../../models/asset.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { UniverseImpactDialogComponent, ImpactDialogChoice } from '../../shared/universe-impact-dialog.component';
import { PartitionTimelineComponent, PartitionCell } from '../../shared/partition-timeline.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import { DataTableColumn } from '../../shared/data-table/data-table.model';
import { FeedRunsTabComponent } from './feed-runs-tab.component';
import { Skeleton } from 'primeng/skeleton';
import { Button } from 'primeng/button';

@Component({
  selector: 'app-feed-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    JsonPipe,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    Card,
    Tag,
    Skeleton,
    Button,
    UniversePanelComponent,
    UniverseImpactDialogComponent,
    PartitionTimelineComponent,
    DataTableComponent,
    FeedRunsTabComponent,
  ],
  templateUrl: './feed-detail.component.html',
})
export class FeedDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  feedService = inject(FeedService);

  tabs = ['Overview', 'Runs', 'Universe', 'Configuration'];
  activeTab = signal('Overview');

  feedId = '';

  errorColumns: DataTableColumn<FeedRunListItem>[] = [
    { field: 'started_at', header: 'Timestamp', cellType: 'date', width: 130 },
    { field: 'error_message', header: 'Error', valueFormatter: (p: any) => p.value ?? 'Unknown error', cellClass: 'text-red-400' },
  ];

  navigateToError = (row: FeedRunListItem) => ['/feeds', this.feedId, 'runs', row.id];

  // Overview / partition state — derived from feed runs
  partitionCells = signal<PartitionCell[]>([]);
  partitionsLoading = signal(false);
  timelinePage = signal(1);
  timelineTotalPages = signal(1);
  overviewStats = signal<{ materialized: number; failed: number; pending: number; total: number }>({
    materialized: 0, failed: 0, pending: 0, total: 0,
  });
  runStats = signal<{ avgDuration: string; avgRecords: string; recentErrors: FeedRunListItem[] }>({
    avgDuration: '-', avgRecords: '-', recentErrors: [],
  });

  // Map partition_key -> run for click navigation
  private partitionRunMap = new Map<string, FeedRunListItem>();

  // Universe state
  universeItems = signal<UniverseItem[]>([]);

  feedScopeMode = computed<'instruments' | 'composites' | null>(() => {
    const feed = this.feedService.selectedFeed();
    if (!feed) return null;
    return feed.scope_type === 'instrument' ? 'instruments' : 'composites';
  });

  private partitionsLoaded = false;

  constructor() {
    effect(() => {
      const feed = this.feedService.selectedFeed();
      if (feed && feed.id === this.feedId && !this.partitionsLoaded) {
        this.partitionsLoaded = true;
        this.loadTimeline();
      }
    });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.feedId) return;
      this.feedId = id;

      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      } else {
        this.activeTab.set('Overview');
      }
      this.partitionsLoaded = false;
      this.partitionCells.set([]);
      this.timelinePage.set(1);

      this.feedService.loadFeedDetail(this.feedId);
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
      default: return 'secondary';
    }
  }

  formatPartitionKey(key: string | null): string {
    if (!key) return '-';
    return new Date(key).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
    });
  }

  // --- Partition timeline (derived from feed runs) ---

  /** Loads a page of feed runs and builds partition cells from them. */
  loadTimeline(): void {
    this.partitionsLoading.set(true);
    // Load 100 runs per page for the timeline (sorted most-recent-first by API)
    const pageSize = 100;
    this.feedService.loadFeedRuns(this.feedId, this.timelinePage(), pageSize).subscribe({
      next: (res) => {
        this.timelineTotalPages.set(res.total_pages);
        this.partitionRunMap.clear();

        // Group runs by partition_key, keeping best status per partition
        const partitionMap = new Map<string, { run: FeedRunListItem; status: string }>();
        for (const run of res.items) {
          const key = run.partition_key ?? run.started_at;
          const existing = partitionMap.get(key);
          const resolvedStatus = this.runToPartitionStatus(run.status);
          if (!existing || this.statusPriority(resolvedStatus) > this.statusPriority(existing.status)) {
            partitionMap.set(key, { run, status: resolvedStatus });
          }
        }

        const cells: PartitionCell[] = [];
        for (const [key, { run, status }] of partitionMap) {
          cells.push({
            partition_key: key,
            status,
            id: run.partition_id,
            window_start: run.started_at,
            window_end: run.completed_at ?? run.started_at,
            run_id: run.id,
          });
          this.partitionRunMap.set(key, run);
        }

        // Sort chronologically (oldest first)
        cells.sort((a, b) => new Date(a.partition_key).getTime() - new Date(b.partition_key).getTime());
        this.partitionCells.set(cells);

        const materialized = cells.filter(c => c.status === 'MATERIALIZED').length;
        const failed = cells.filter(c => c.status === 'FAILED').length;
        const pending = cells.filter(c => c.status === 'PENDING').length;
        this.overviewStats.set({ materialized, failed, pending, total: cells.length });

        // Compute run stats from the raw runs
        const completedRuns = res.items.filter(r => r.completed_at && r.started_at);
        const durations = completedRuns.map(r =>
          new Date(r.completed_at!).getTime() - new Date(r.started_at).getTime()
        );
        const avgDurationMs = durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length : 0;
        const recordRuns = res.items.filter(r => r.records_fetched != null);
        const avgRecords = recordRuns.length > 0
          ? Math.round(recordRuns.reduce((a, r) => a + r.records_fetched!, 0) / recordRuns.length) : 0;
        const recentErrors = res.items.filter(r => r.status === 'FAILED').slice(0, 5);
        this.runStats.set({
          avgDuration: avgDurationMs > 0 ? (avgDurationMs < 1000 ? `${Math.round(avgDurationMs)}ms` : `${(avgDurationMs / 1000).toFixed(1)}s`) : '-',
          avgRecords: recordRuns.length > 0 ? avgRecords.toLocaleString() : '-',
          recentErrors,
        });
        this.partitionsLoading.set(false);
      },
      error: () => this.partitionsLoading.set(false),
    });
  }

  /** Map run status to partition display status. */
  private runToPartitionStatus(runStatus: string): string {
    switch (runStatus) {
      case 'COMPLETED': return 'MATERIALIZED';
      case 'FAILED': return 'FAILED';
      default: return 'PENDING';
    }
  }

  /** Higher priority wins when multiple runs share a partition. */
  private statusPriority(status: string): number {
    switch (status) {
      case 'MATERIALIZED': return 3;
      case 'FAILED': return 2;
      case 'PENDING': return 1;
      default: return 0;
    }
  }

  onPartitionClick(cell: PartitionCell): void {
    if (cell.run_id) {
      this.router.navigate(['/feeds', this.feedId, 'runs', cell.run_id]);
    }
  }

  timelineNewer(): void {
    const p = this.timelinePage();
    if (p > 1) {
      this.timelinePage.set(p - 1);
      this.loadTimeline();
    }
  }

  timelineOlder(): void {
    const p = this.timelinePage();
    if (p < this.timelineTotalPages()) {
      this.timelinePage.set(p + 1);
      this.loadTimeline();
    }
  }

  /** Label for the current timeline window based on the first/last cells. */
  timelineRangeLabel(): string {
    const cells = this.partitionCells();
    if (cells.length === 0) return '';
    const first = new Date(cells[0].partition_key);
    const last = new Date(cells[cells.length - 1].partition_key);
    const fmt = (d: Date) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    return `${fmt(first)} — ${fmt(last)}`;
  }

  successRate(): string {
    const s = this.overviewStats();
    if (s.total === 0) return '-';
    return ((s.materialized / s.total) * 100).toFixed(1) + '%';
  }

  // --- Universe methods ---

  loadUniverse(): void {
    this.feedService.loadFeedUniverse(this.feedId).subscribe({
      next: items => this.universeItems.set(items),
    });
  }

  onAddInstruments(event: { instrumentIds: string[]; startOrder: number }): void {
    this.feedService.batchAddFeedInstruments(this.feedId, event.instrumentIds, event.startOrder).subscribe({
      next: () => this.toast.success(`${event.instrumentIds.length} instrument(s) added to universe`),
      error: () => this.toast.error('Failed to add instruments to universe'),
    });
  }

  removeUniverseItem(instrumentId: string): void {
    this.openImpactDialog({
      label: 'Instrument',
      load: this.feedService.getFeedUniverseImpact(this.feedId, instrumentId),
      remove: () => this.feedService.removeFeedUniverseItem(this.feedId, instrumentId),
      disable: () => this.feedService.setFeedUniverseItemActive(this.feedId, instrumentId, false),
    });
  }

  onAddComposites(event: { compositeIds: string[]; startOrder: number }): void {
    this.feedService.batchAddFeedComposites(this.feedId, event.compositeIds, event.startOrder).subscribe({
      next: () => this.toast.success(`${event.compositeIds.length} composite(s) added to universe`),
      error: () => this.toast.error('Failed to add composites to universe'),
    });
  }

  removeCompositeItem(compositeId: string): void {
    this.openImpactDialog({
      label: 'Composite',
      load: this.feedService.getFeedCompositeUniverseImpact(this.feedId, compositeId),
      remove: () => this.feedService.removeFeedCompositeUniverseItem(this.feedId, compositeId),
      disable: () => this.feedService.setFeedCompositeUniverseItemActive(this.feedId, compositeId, false),
    });
  }

  onToggleInstrumentActive(event: { id: string; isActive: boolean }): void {
    this.feedService.setFeedUniverseItemActive(this.feedId, event.id, event.isActive).subscribe({
      next: () => this.toast.success(event.isActive ? 'Instrument enabled' : 'Instrument disabled'),
      error: (err) => this.toast.error(err?.error?.message ?? 'Failed to update instrument'),
    });
  }

  onToggleCompositeActive(event: { id: string; isActive: boolean }): void {
    this.feedService.setFeedCompositeUniverseItemActive(this.feedId, event.id, event.isActive).subscribe({
      next: () => this.toast.success(event.isActive ? 'Composite enabled' : 'Composite disabled'),
      error: (err) => this.toast.error(err?.error?.message ?? 'Failed to update composite'),
    });
  }

  // --- Impact dialog plumbing ---

  impactDialogVisible = signal(false);
  impactReport = signal<ImpactReport | null>(null);
  impactBusy = signal(false);
  impactEntityLabel = signal('Item');
  impactEntityName = signal<string | null>(null);
  impactSupportsDisable = signal(true);

  private impactCurrent: {
    remove: () => import('rxjs').Observable<any>;
    disable: () => import('rxjs').Observable<any>;
    successMessage: string;
    disableMessage: string;
  } | null = null;

  private openImpactDialog(opts: {
    label: string;
    load: import('rxjs').Observable<ImpactReport>;
    remove: () => import('rxjs').Observable<any>;
    disable: () => import('rxjs').Observable<any>;
  }): void {
    this.impactCurrent = {
      remove: opts.remove,
      disable: opts.disable,
      successMessage: `${opts.label} removed`,
      disableMessage: `${opts.label} disabled`,
    };
    this.impactEntityLabel.set(opts.label);
    this.impactEntityName.set(null);
    this.impactReport.set(null);
    this.impactBusy.set(false);
    this.impactSupportsDisable.set(true);
    this.impactDialogVisible.set(true);

    opts.load.subscribe({
      next: (report) => this.impactReport.set(report),
      error: () => {
        this.toast.error('Failed to compute impact');
        this.impactDialogVisible.set(false);
      },
    });
  }

  onImpactDecision(choice: ImpactDialogChoice): void {
    if (choice === 'cancel') {
      this.impactDialogVisible.set(false);
      this.impactCurrent = null;
      return;
    }
    const op = this.impactCurrent;
    if (!op) return;
    this.impactBusy.set(true);
    const stream = choice === 'remove' ? op.remove() : op.disable();
    stream.subscribe({
      next: () => {
        this.toast.success(choice === 'remove' ? op.successMessage : op.disableMessage);
        this.impactBusy.set(false);
        this.impactDialogVisible.set(false);
        this.impactCurrent = null;
      },
      error: (err) => {
        this.impactBusy.set(false);
        const msg = err?.error?.message ?? `Failed to ${choice} item`;
        this.toast.error(msg);
      },
    });
  }
}
