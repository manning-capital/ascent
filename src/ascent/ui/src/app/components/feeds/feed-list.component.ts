import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FeedService } from '../../services/feed.service';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-feed-list',
  standalone: true,
  imports: [DatePipe, TableModule, Card, Tag, InputText, Select, Skeleton],
  templateUrl: './feed-list.component.html',
})
export class FeedListComponent implements OnInit {
  private router = inject(Router);
  feedService = inject(FeedService);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  ngOnInit(): void {
    this.feedService.loadFeeds();
  }

  navigateToFeed(id: string): void {
    this.router.navigate(['/feeds', id]);
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

  statusSeverity(status: string | null): 'success' | 'danger' | 'warn' | 'secondary' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'FAILED': return 'danger';
      case 'RUNNING': return 'warn';
      default: return 'secondary';
    }
  }
}
