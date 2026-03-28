import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FeedService } from '../../services/feed.service';
import { StatCardComponent } from '../shared/stat-card.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../shared/empty-state.component';

@Component({
  selector: 'app-feed-list',
  standalone: true,
  imports: [RouterLink, DatePipe, StatCardComponent, Card, Skeleton, EmptyStateComponent],
  templateUrl: './feed-list.component.html',
})
export class FeedListComponent implements OnInit {
  feedService = inject(FeedService);

  ngOnInit(): void {
    this.feedService.loadFeeds();
  }

  statusClass(status: string | null): string {
    switch (status) {
      case 'COMPLETED': return 'text-green-500';
      case 'FAILED': return 'text-red-500';
      case 'RUNNING': return 'text-warning';
      default: return 'text-surface-500';
    }
  }

  scheduleLabel(schedule: Record<string, any> | null): string {
    if (!schedule) return 'Triggered';
    const interval = schedule['interval'];
    if (!interval) return 'Triggered';
    if (interval < 60) return `${interval}s`;
    if (interval < 3600) return `${Math.round(interval / 60)}m`;
    if (interval < 86400) return `${Math.round(interval / 3600)}h`;
    return `${Math.round(interval / 86400)}d`;
  }
}
