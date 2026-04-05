import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FeedService } from '../../../services/feed.service';
import { StrategyService } from '../../../services/strategy.service';
import { StrategyRunListItem, StrategyFeedDAG } from '../../../models/feed.model';
import { FeedDagComponent, FeedRunStatusOverride } from '../strategy-detail/feed-dag.component';
import { RunDetailCardComponent, RunDetailField, RunDetailItem } from '../../shared/run-detail-card.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { DataTableComponent } from '../../shared/data-table/data-table.component';
import type { DataTableColumn } from '../../shared/data-table/data-table.model';

@Component({
  selector: 'app-strategy-run-detail',
  standalone: true,
  imports: [
    RouterLink,
    Tabs, TabList, Tab,
    Panel,
    Tag,
    Skeleton,
    RunDetailCardComponent,
    FeedDagComponent,
    DataTableComponent,
  ],
  templateUrl: './strategy-run-detail.component.html',
})
export class StrategyRunDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private feedService = inject(FeedService);
  private strategyService = inject(StrategyService);

  tabs = ['Overview', 'DAG'];
  strategyId = '';
  activeTab = signal('Overview');
  loading = signal(true);
  run = signal<StrategyRunListItem | null>(null);
  feedDag = signal<StrategyFeedDAG | null>(null);

  strategyName = computed(() => this.strategyService.selectedStrategy()?.name ?? '');

  feedRunColumns: DataTableColumn[] = [
    { field: 'feed_id', header: 'Feed', cellType: 'monospace' },
    { field: 'status', header: 'Status', cellType: 'tag', tagMapper: (v: string) => {
      const map: Record<string, string> = { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warn' };
      return { label: v, severity: map[v] ?? 'secondary' };
    }},
    { field: 'is_trigger', header: 'Trigger', valueFormatter: (p: any) => p.value ? 'Yes' : '-' },
  ];

  runDetailItem = computed<RunDetailItem | null>(() => {
    const r = this.run();
    if (!r) return null;
    return { ...r, feed_count: r.feed_runs.length };
  });

  extraFields: RunDetailField[] = [
    { label: 'Trigger Feed', key: 'trigger_feed_id' },
    { label: 'Feeds', key: 'feed_count' },
  ];

  feedRunStatuses = computed<Map<string, FeedRunStatusOverride> | null>(() => {
    const r = this.run();
    if (!r || r.feed_runs.length === 0) return null;
    const map = new Map<string, FeedRunStatusOverride>();
    for (const fr of r.feed_runs) {
      map.set(fr.feed_id, { status: fr.status, is_trigger: fr.is_trigger, feed_run_id: fr.feed_run_id });
    }
    return map;
  });

  statusSeverity(status: string): 'success' | 'danger' | 'warn' | 'secondary' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      case 'PENDING': return 'secondary';
      default: return 'secondary';
    }
  }

  skeletonRows(count: number): number[] {
    return Array.from({ length: count }, (_, i) => i);
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
    this.router.navigate([], { relativeTo: this.route, queryParams: { tab }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      const runId = params.get('runId')!;

      const qp = this.route.snapshot.queryParamMap;
      const tab = qp.get('tab');
      if (tab && this.tabs.includes(tab)) {
        this.activeTab.set(tab);
      }

      if (id !== this.strategyId) {
        this.strategyId = id;
        this.strategyService.loadStrategyDetail(this.strategyId);
        this.feedService.loadStrategyFeedDAG(this.strategyId).subscribe({
          next: (dag) => this.feedDag.set(dag),
        });
      }

      this.loading.set(true);
      this.run.set(null);

      this.feedService.getStrategyRun(this.strategyId, runId).subscribe({
        next: (run) => {
          this.run.set(run);
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
        },
      });
    });
  }
}
