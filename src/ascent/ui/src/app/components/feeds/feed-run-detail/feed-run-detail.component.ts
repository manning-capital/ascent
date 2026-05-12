import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Splitter } from 'primeng/splitter';
import { Tag } from 'primeng/tag';
import { Skeleton } from 'primeng/skeleton';
import { Message } from 'primeng/message';
import { FeedService } from '../../../services/feed.service';
import { FeedRunDetail } from '../../../models/feed.model';
import { FeedRunTopPanelComponent } from './feed-run-top-panel.component';
import { FeedRunBottomPanelComponent } from './feed-run-bottom-panel.component';
import { FeedRunStatsRailComponent } from './feed-run-stats-rail.component';
import { AppPageHeaderComponent, AppBreadcrumbItem } from '../../ui/page-header/app-page-header.component';

const RAIL_COLLAPSED_KEY = 'feed-run-detail-rail-collapsed';

@Component({
  selector: 'app-feed-run-detail',
  standalone: true,
  imports: [
    Splitter,
    Tag,
    Skeleton,
    Message,
    FeedRunTopPanelComponent,
    FeedRunBottomPanelComponent,
    FeedRunStatsRailComponent,
    AppPageHeaderComponent,
  ],
  templateUrl: './feed-run-detail.component.html',
  host: { class: 'flex flex-col h-full min-h-0' },
})
export class FeedRunDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private feedService = inject(FeedService);

  feedId = '';
  runId = '';

  run = signal<FeedRunDetail | null>(null);
  loading = signal(true);

  railCollapsed = signal<boolean>(this.loadRailCollapsed());

  vSizes = [40, 60];
  hSizes = computed<number[]>(() => (this.railCollapsed() ? [97, 3] : [80, 20]));

  feedDisplayName = computed(() => this.feedService.selectedFeed()?.display_name ?? 'Feed');

  breadcrumb = computed<AppBreadcrumbItem[]>(() => [
    { label: 'Feeds', routerLink: '/feeds' },
    { label: this.feedDisplayName(), routerLink: ['/feeds', this.feedId] },
  ]);

  constructor() {
    effect(() => {
      try {
        localStorage.setItem(RAIL_COLLAPSED_KEY, this.railCollapsed() ? '1' : '0');
      } catch {
        // ignore
      }
    });
  }

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

  private loadRailCollapsed(): boolean {
    try {
      return localStorage.getItem(RAIL_COLLAPSED_KEY) === '1';
    } catch {
      return false;
    }
  }
}
