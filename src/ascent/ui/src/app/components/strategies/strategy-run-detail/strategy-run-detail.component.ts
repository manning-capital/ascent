import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FeedService } from '../../../services/feed.service';
import { StrategyService } from '../../../services/strategy.service';
import { StrategyRunListItem, StrategyFeedDAG } from '../../../models/feed.model';
import { FeedDagComponent, FeedRunStatusOverride } from '../strategy-detail/feed-dag.component';
import { RunDetailCardComponent, RunDetailField, RunDetailItem } from '../../shared/run-detail-card.component';
import { Tabs, TabList, Tab } from 'primeng/tabs';
import { Panel } from 'primeng/panel';
import { Tag } from 'primeng/tag';
import { TableModule } from 'primeng/table';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-strategy-run-detail',
  standalone: true,
  imports: [
    RouterLink,
    Tabs, TabList, Tab,
    Panel,
    Tag,
    TableModule,
    Skeleton,
    RunDetailCardComponent,
    FeedDagComponent,
  ],
  templateUrl: './strategy-run-detail.component.html',
})
export class StrategyRunDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private feedService = inject(FeedService);
  private strategyService = inject(StrategyService);

  strategyId = '';
  activeTab = signal('Overview');
  loading = signal(true);
  run = signal<StrategyRunListItem | null>(null);
  feedDag = signal<StrategyFeedDAG | null>(null);

  strategyName = computed(() => this.strategyService.selectedStrategy()?.name ?? '');

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
      default: return 'info';
    }
  }

  skeletonRows(count: number): number[] {
    return Array.from({ length: count }, (_, i) => i);
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      const runId = params.get('runId')!;

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
