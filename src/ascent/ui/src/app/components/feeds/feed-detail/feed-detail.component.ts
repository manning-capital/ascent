import { Component, computed, effect, inject, OnInit, signal, viewChild } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { JsonPipe } from '@angular/common';
import { FeedService } from '../../../services/feed.service';
import { ToastService } from '../../../services/toast.service';
import { FeedRunListItem } from '../../../models/feed.model';
import { ImpactReport, UniverseItem } from '../../../models/asset.model';
import { UniversePanelComponent } from '../../shared/universe-panel.component';
import { UniverseImpactDialogComponent, ImpactDialogChoice } from '../../shared/universe-impact-dialog.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { SchemaFormComponent } from '../../shared/schema-form.component';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import { DataTableColumn } from '../../shared/data-table/data-table.model';
import { FeedRunsTabComponent } from './feed-runs-tab.component';
import { FeedActivityTimelineComponent } from './feed-activity-timeline.component';
import { StatCardComponent } from '../../shared/stat-card.component';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';
import { Skeleton } from 'primeng/skeleton';

export interface RecentRunPill {
  id: string;
  snapshot_timestamp: string;
  status: string;
  started_at: string;
  completed_at: string | null;
}

@Component({
  selector: 'app-feed-detail',
  standalone: true,
  imports: [
    RouterLink,
    JsonPipe,
    Tabs, TabList, Tab,
    SchemaFormComponent,
    Card,
    Tag,
    Skeleton,
    UniversePanelComponent,
    UniverseImpactDialogComponent,
    DataTableComponent,
    FeedRunsTabComponent,
    FeedActivityTimelineComponent,
    StatCardComponent,
    FieldPanelComponent,
  ],
  templateUrl: './feed-detail.component.html',
})
export class FeedDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private toast = inject(ToastService);
  feedService = inject(FeedService);
  private universePanel = viewChild(UniversePanelComponent);

  tabs = ['Overview', 'Runs', 'Universe', 'Configuration'];
  activeTab = signal('Overview');

  feedId = '';

  errorColumns: DataTableColumn<FeedRunListItem>[] = [
    { field: 'started_at', header: 'Timestamp', cellType: 'date', width: 130 },
    { field: 'error_message', header: 'Error', valueFormatter: (p: any) => p.value ?? 'Unknown error', cellClass: 'text-negative' },
  ];

  navigateToError = (row: FeedRunListItem) => ['/feeds', this.feedId, 'runs', row.id];

  // Overview state — a rolling window of recent runs and derived stats.
  recentRuns = signal<RecentRunPill[]>([]);
  runsLoading = signal(false);
  overviewStats = signal<{ completed: number; failed: number; running: number; total: number }>({
    completed: 0, failed: 0, running: 0, total: 0,
  });
  runStats = signal<{ avgDuration: string; avgRecords: string; recentErrors: FeedRunListItem[] }>({
    avgDuration: '-', avgRecords: '-', recentErrors: [],
  });

  universeItems = signal<UniverseItem[]>([]);

  feedScopeMode = computed<'instruments' | 'composites' | null>(() => {
    const feed = this.feedService.selectedFeed();
    if (!feed) return null;
    return feed.scope_type === 'instrument' ? 'instruments' : 'composites';
  });

  lastRunRelative = computed(() => {
    const iso = this.feedService.selectedFeed()?.last_run_at ?? null;
    return this.relativeTime(iso);
  });

  hasErrors = computed(() => this.runStats().recentErrors.length > 0);

  identityFields = computed<PanelField[]>(() => {
    const f = this.feedService.selectedFeed();
    if (!f) return [];
    return [
      { label: 'Display Name', key: 'display_name', type: 'text', value: f.display_name },
      { label: 'Internal Name', key: 'name', type: 'mono', value: f.name },
      { label: 'Feed Ref', key: 'feed_ref', type: 'mono', value: f.feed_ref },
      { label: 'Channel', key: 'channel', type: 'mono', value: f.channel },
    ];
  });

  sourceScopeFields = computed<PanelField[]>(() => {
    const f = this.feedService.selectedFeed();
    if (!f) return [];
    return [
      { label: 'Provider', key: 'provider', type: 'text', value: f.provider_name ?? '—' },
      { label: 'Scope', key: 'scope', type: 'text', value: this.capitalize(f.scope_type) },
      {
        label: f.scope_type === 'instrument' ? 'Instrument Type' : 'Composite Type',
        key: 'scopeType',
        type: 'text',
        value: f.scope_type_name ?? '—',
      },
      { label: 'Output Table', key: 'output_table', type: 'mono', value: f.output_table },
    ];
  });

  scheduleFields = computed<PanelField[]>(() => {
    const f = this.feedService.selectedFeed();
    if (!f) return [];
    return [
      { label: 'Schedule', key: 'schedule', type: 'text', value: this.scheduleLabel(f.schedule) },
      { label: 'Active', key: 'active', type: 'active', value: f.is_active },
    ];
  });

  auditFields = computed<PanelField[]>(() => {
    const f = this.feedService.selectedFeed();
    if (!f) return [];
    const fields: PanelField[] = [
      { label: 'ID', key: 'id', type: 'mono', value: f.id },
    ];
    if (f.created_at) fields.push({ label: 'Created', key: 'created', type: 'date', value: f.created_at });
    if (f.updated_at) fields.push({ label: 'Updated', key: 'updated', type: 'date', value: f.updated_at });
    return fields;
  });

  outputSchemaRows = computed<Array<{ name: string; dtype: string; nullable: string; description: string }>>(() => {
    const schema = this.feedService.selectedFeed()?.data_schema;
    const cols = schema && typeof schema === 'object' ? (schema as any)['columns'] : null;
    if (!cols || typeof cols !== 'object') return [];
    return Object.entries(cols).map(([name, def]) => ({
      name,
      dtype: (def as any)?.dtype ?? '—',
      nullable: (def as any)?.nullable ? 'Yes' : 'No',
      description: (def as any)?.description ?? '',
    }));
  });

  outputSchemaColumns: DataTableColumn<any>[] = [
    { field: 'name', header: 'Column', cellType: 'monospace', width: 200 },
    { field: 'dtype', header: 'Type', cellType: 'monospace', width: 160 },
    { field: 'nullable', header: 'Nullable', width: 100 },
    { field: 'description', header: 'Description' },
  ];

  private runsLoaded = false;

  constructor() {
    effect(() => {
      const feed = this.feedService.selectedFeed();
      if (feed && feed.id === this.feedId && !this.runsLoaded) {
        this.runsLoaded = true;
        this.loadRecentRuns();
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
      this.runsLoaded = false;
      this.recentRuns.set([]);

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

  private capitalize(s: string): string {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  private relativeTime(iso: string | null): string {
    if (!iso) return 'Never';
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 0) return 'just now';
    if (diff < 60_000) return 'just now';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)}d ago`;
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
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

  // --- Recent runs loader (overview) ---

  loadRecentRuns(): void {
    this.runsLoading.set(true);
    const pageSize = 100;
    this.feedService.loadFeedRuns(this.feedId, 1, pageSize).subscribe({
      next: (res) => {
        const runs = res.items;
        this.recentRuns.set(
          runs.map(r => ({
            id: r.id,
            snapshot_timestamp: r.snapshot_timestamp,
            status: r.status,
            started_at: r.started_at,
            completed_at: r.completed_at,
          })),
        );

        const completed = runs.filter(r => r.status === 'COMPLETED').length;
        const failed = runs.filter(r => r.status === 'FAILED').length;
        const running = runs.filter(r => r.status === 'RUNNING').length;
        this.overviewStats.set({ completed, failed, running, total: runs.length });

        const completedRuns = runs.filter(r => r.completed_at && r.started_at);
        const durations = completedRuns.map(r =>
          new Date(r.completed_at!).getTime() - new Date(r.started_at).getTime()
        );
        const avgDurationMs = durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length : 0;
        const recordRuns = runs.filter(r => r.records_fetched != null);
        const avgRecords = recordRuns.length > 0
          ? Math.round(recordRuns.reduce((a, r) => a + r.records_fetched!, 0) / recordRuns.length) : 0;
        const recentErrors = runs.filter(r => r.status === 'FAILED').slice(0, 5);
        this.runStats.set({
          avgDuration: avgDurationMs > 0 ? (avgDurationMs < 1000 ? `${Math.round(avgDurationMs)}ms` : `${(avgDurationMs / 1000).toFixed(1)}s`) : '-',
          avgRecords: recordRuns.length > 0 ? avgRecords.toLocaleString() : '-',
          recentErrors,
        });
        this.runsLoading.set(false);
      },
      error: () => this.runsLoading.set(false),
    });
  }

  onPillClick(runId: string): void {
    this.router.navigate(['/feeds', this.feedId, 'runs', runId]);
  }

  successRate(): string {
    const s = this.overviewStats();
    if (s.total === 0) return '-';
    return ((s.completed / s.total) * 100).toFixed(1) + '%';
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
        this.universePanel()?.refresh();
      },
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
      next: () => {
        this.toast.success(`${event.compositeIds.length} composite(s) added to universe`);
        this.universePanel()?.refresh();
      },
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
